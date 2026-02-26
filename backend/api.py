import logging
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

import pandas as pd
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.schemas import (
    JobStatusResponse,
    LoginRequest,
    LogoutRequest,
    ProcessResponse,
    RefreshRequest,
    RegisterRequest,
    ResultsResponse,
    TokenPairResponse,
    UploadResponse,
    UserProfileResponse,
)
from config.settings import settings
from src.core.data_loader import DataLoader, DataValidationError
from src.core.job_manager import JobManager
from src.core.model_runner import ModelRunner
from src.core.analysis_engine import AnalysisEngine
from config.schemas import ProcessingParameters
from src.core.auth_service import AuthService

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

job_manager = JobManager()
auth_service = AuthService(job_manager)


class AuthError(Exception):
    pass


def _get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = credentials.credentials
    try:
        return auth_service.verify_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _require_role(required_role: str):
    def dependency(user: dict[str, str] = Depends(_get_current_user)) -> dict[str, str]:
        role = user.get("role", "user")
        if role != required_role:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return dependency


def _to_user_profile(user: dict[str, Any]) -> UserProfileResponse:
    return UserProfileResponse(
        user_id=user["user_id"],
        email=user.get("email") or "",
        full_name=user.get("full_name"),
        role=user.get("role", "user"),
        is_active=bool(user.get("is_active", 1)),
        created_at=user.get("created_at") or "",
        last_seen_at=user.get("last_seen_at") or "",
    )


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    openapi_tags = [
        {
            "name": "auth",
            "description": (
                "Authentication endpoints for local account management. "
                "Use `register` or `login` to obtain an access token and refresh token. "
                "Send access token in `Authorization: Bearer <token>` for protected routes."
            ),
        },
        {
            "name": "jobs",
            "description": "User-owned analysis job lifecycle: upload, process, status, results, export.",
        },
        {
            "name": "admin",
            "description": "Admin-only endpoints requiring role `admin`.",
        },
        {
            "name": "system",
            "description": "Service health and operational endpoints.",
        },
    ]

    app = FastAPI(
        title="OASIS Backend API",
        version="0.2.0",
        description=(
            "Standalone backend service for user-owned analysis jobs.\n\n"
            "### Authentication Flow\n"
            "1. `POST /auth/register` to create an account or `POST /auth/login` to authenticate.\n"
            "2. Store returned `access_token` and `refresh_token`.\n"
            "3. Use `Authorization: Bearer <access_token>` on protected endpoints.\n"
            "4. When access token expires, call `POST /auth/refresh` with `refresh_token`.\n"
            "5. Call `POST /auth/logout` to revoke a refresh token session."
        ),
        openapi_tags=openapi_tags,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        if settings.environment != "development" and len(settings.jwt_secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 bytes outside development environment")
        logger.info(
            "Backend started on %s:%s | data_dir=%s",
            settings.host,
            settings.port,
            settings.data_dir,
        )

    @app.get("/health", tags=["system"])
    async def health() -> dict:
        return {"status": "ok"}

    @app.post(
        "/auth/register",
        response_model=TokenPairResponse,
        tags=["auth"],
        summary="Register a new user",
        description=(
            "Creates a new local user account with email and password, then immediately issues "
            "an access token and refresh token."
        ),
        responses={
            200: {"description": "User created and token pair issued"},
            400: {"description": "Invalid payload or email already exists"},
        },
    )
    async def register(payload: RegisterRequest) -> TokenPairResponse:
        try:
            user = auth_service.register_user(
                email=payload.email,
                password=payload.password,
                full_name=payload.full_name,
                role="user",
            )
            tokens = auth_service.issue_token_pair(user)
            return TokenPairResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_in=tokens["expires_in"],
                user=_to_user_profile(user),
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.post(
        "/auth/login",
        response_model=TokenPairResponse,
        tags=["auth"],
        summary="Login with email and password",
        description="Authenticates credentials and returns a fresh access/refresh token pair.",
        responses={
            200: {"description": "Authentication successful"},
            401: {"description": "Invalid email/password or inactive user"},
        },
    )
    async def login(payload: LoginRequest) -> TokenPairResponse:
        try:
            user = auth_service.authenticate_user(email=payload.email, password=payload.password)
            tokens = auth_service.issue_token_pair(user)
            return TokenPairResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_in=tokens["expires_in"],
                user=_to_user_profile(user),
            )
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error))

    @app.post(
        "/auth/refresh",
        response_model=TokenPairResponse,
        tags=["auth"],
        summary="Refresh access token",
        description=(
            "Rotates refresh session and returns a new token pair. "
            "Old refresh token is revoked after successful refresh."
        ),
        responses={
            200: {"description": "Token pair rotated successfully"},
            401: {"description": "Refresh token invalid, expired, or revoked"},
        },
    )
    async def refresh(payload: RefreshRequest) -> TokenPairResponse:
        try:
            tokens = auth_service.refresh_tokens(payload.refresh_token)
            claims = auth_service.verify_access_token(tokens["access_token"])
            user = job_manager.get_user_by_id(claims["user_id"])
            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            return TokenPairResponse(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type=tokens["token_type"],
                expires_in=tokens["expires_in"],
                user=_to_user_profile(user),
            )
        except ValueError as error:
            raise HTTPException(status_code=401, detail=str(error))

    @app.post(
        "/auth/logout",
        tags=["auth"],
        summary="Logout and revoke refresh token",
        description=(
            "Revokes the supplied refresh token session. "
            "Requires a valid access token to authenticate the caller."
        ),
        responses={
            200: {"description": "Refresh token revoked"},
            400: {"description": "Refresh token malformed or already invalid"},
            401: {"description": "Missing or invalid access token"},
        },
    )
    async def logout(payload: LogoutRequest, _: dict = Depends(_get_current_user)) -> dict:
        try:
            auth_service.revoke_refresh_token(payload.refresh_token)
            return {"status": "ok"}
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))

    @app.get(
        "/auth/me",
        response_model=UserProfileResponse,
        tags=["auth"],
        summary="Get current user profile",
        description="Returns the authenticated user profile resolved from the access token subject.",
        responses={
            200: {"description": "Profile resolved"},
            401: {"description": "Missing or invalid access token"},
            404: {"description": "User no longer exists"},
        },
    )
    async def me(user: dict = Depends(_get_current_user)) -> UserProfileResponse:
        resolved = job_manager.get_user_by_id(user["user_id"])
        if not resolved:
            raise HTTPException(status_code=404, detail="User not found")
        return _to_user_profile(resolved)

    @app.get("/admin/users", tags=["admin"])
    async def admin_list_users(
        limit: int = 200,
        _: dict = Depends(_require_role("admin")),
    ) -> dict:
        return {"users": job_manager.list_users(limit=limit)}

    @app.get("/jobs", tags=["jobs"])
    async def list_jobs(
        status: Optional[str] = None,
        limit: int = 100,
        user: dict = Depends(_get_current_user),
    ) -> dict:
        jobs = job_manager.list_jobs_for_user(user_id=user["user_id"], status=status, limit=limit)
        return {"jobs": jobs}

    @app.post("/upload", response_model=UploadResponse, tags=["jobs"])
    async def upload_file(
        file: UploadFile = File(...),
        dataset_name: Optional[str] = Form(None),
        catchment_threshold_area: Optional[float] = Form(None),
        user: dict = Depends(_get_current_user),
    ) -> UploadResponse:
        try:
            file_ext = Path(file.filename or "").suffix.lower()
            if file_ext not in settings.allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{file_ext}'. Allowed: {', '.join(sorted(settings.allowed_extensions))}",
                )

            user_id = user["user_id"]
            job_manager.create_user_if_missing(user_id=user_id, email=user.get("email"))

            parameters = {
                "dataset_name": dataset_name or file.filename or "dataset.csv",
                "catchment_threshold_area": catchment_threshold_area,
            }
            job = job_manager.create_job(user_id=user_id, parameters=parameters)
            job_id = job["job_id"]

            content = await file.read()
            upload_path = job_manager.save_upload(user_id, job_id, file.filename or "data.csv", content)

            try:
                loader = DataLoader(upload_path)
                dataframe = loader.load()
                sample_count = loader.get_sample_count()
                model_type = ModelRunner.determine_model_type(dataframe)
                logger.info("Job %s validated %s samples", job_id, sample_count)
            except DataValidationError as error:
                job_manager.update_status_for_user(
                    user_id,
                    job_id,
                    "failed",
                    error_message=str(error),
                )
                raise HTTPException(status_code=400, detail=str(error))

            job_manager.update_status_for_user(
                user_id,
                job_id,
                "queued",
                progress_percent=0.0,
                parameters={**parameters, "sample_count": sample_count, "model_type": model_type},
            )

            return UploadResponse(
                job_id=job_id,
                status="queued",
                dataset_name=parameters["dataset_name"],
                sample_count=sample_count,
                user_id=user_id,
            )

        except HTTPException:
            raise
        except Exception as error:
            logger.error("Upload failed: %s", traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Internal server error: {error}")

    @app.post("/process/{job_id}", response_model=ProcessResponse, tags=["jobs"])
    async def process_job(
        job_id: str,
        background_tasks: BackgroundTasks,
        user: dict = Depends(_get_current_user),
    ) -> ProcessResponse:
        user_id = user["user_id"]
        job = job_manager.get_job_for_user(user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        if job["status"] != "queued":
            raise HTTPException(
                status_code=400,
                detail=f"Job '{job_id}' cannot be processed (current status: {job['status']})",
            )

        job_manager.update_status_for_user(user_id, job_id, "processing", progress_percent=1.0, error_message=None)
        background_tasks.add_task(_run_analysis, user_id, job_id)

        return ProcessResponse(
            job_id=job_id,
            status="processing",
            progress_percent=1.0,
            user_id=user_id,
            message="Processing started",
        )

    @app.get("/status/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
    async def get_job_status(job_id: str, user: dict = Depends(_get_current_user)) -> JobStatusResponse:
        user_id = user["user_id"]
        job = job_manager.get_job_for_user(user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        return JobStatusResponse(
            job_id=job["job_id"],
            status=job["status"],
            progress_percent=float(job.get("progress_percent") or 0.0),
            error_message=job.get("error_message"),
            user_id=user_id,
            created_at=job["created_at"],
            completed_at=job.get("completed_at"),
        )

    @app.get("/results/{job_id}", response_model=ResultsResponse, tags=["jobs"])
    async def get_results(job_id: str, user: dict = Depends(_get_current_user)) -> ResultsResponse:
        user_id = user["user_id"]
        job = job_manager.get_job_for_user(user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        if job["status"] == "processing":
            return JSONResponse(
                status_code=202,
                content={"detail": "Job still processing. Try again in a few seconds."},
            )

        if job["status"] == "failed":
            raise HTTPException(
                status_code=500,
                detail=job.get("error_message") or "Job failed",
            )

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job status is '{job['status']}', expected 'completed'",
            )

        results_csv = job.get("results_csv")
        if not results_csv:
            raise HTTPException(status_code=500, detail="Results CSV missing for completed job")

        csv_path = Path(results_csv)
        if not csv_path.exists():
            raise HTTPException(status_code=500, detail="Results CSV file not found")

        dataframe = pd.read_csv(csv_path)
        params = job.get("parameters", {})
        rows = dataframe.where(pd.notnull(dataframe), None).to_dict(orient="records")

        summary = {
            "total_rows": int(len(dataframe)),
            "columns": list(dataframe.columns),
            "models_run": params.get("models_run", []),
        }

        return ResultsResponse(
            job_id=job_id,
            user_id=user_id,
            dataset_name=params.get("dataset_name", "Unknown"),
            sample_count=int(params.get("sample_count", len(dataframe))),
            csv_file_name=csv_path.name,
            csv_columns=list(dataframe.columns),
            rows=rows,
            summary=summary,
            model_type=params.get("model_type"),
        )

    @app.get("/export/{job_id}", tags=["jobs"])
    async def export_results(job_id: str, format: str = "csv", user: dict = Depends(_get_current_user)) -> FileResponse:
        if format.lower() != "csv":
            raise HTTPException(status_code=400, detail="Unsupported format. Only 'csv' is supported.")

        user_id = user["user_id"]
        job = job_manager.get_job_for_user(user_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot export: job status is '{job['status']}'",
            )

        results_csv = job.get("results_csv")
        if not results_csv:
            raise HTTPException(status_code=500, detail="No CSV artifact available for this job")

        csv_path = Path(results_csv)
        if not csv_path.exists():
            raise HTTPException(status_code=500, detail="CSV artifact not found")

        return FileResponse(
            path=csv_path,
            media_type="text/csv",
            filename=f"{job_id}_contributions.csv",
        )

    return app


def _run_analysis(user_id: str, job_id: str) -> None:
    try:
        logger.info("Starting analysis for job %s (user=%s)", job_id, user_id)

        job = job_manager.get_job_for_user(user_id, job_id)
        if not job:
            logger.error("Job %s not found for user %s", job_id, user_id)
            return

        input_file = job.get("input_file")
        if not input_file:
            raise ValueError("Input file is missing for this job")

        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        output_dir = settings.data_dir / "outputs" / user_id / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        started = perf_counter()
        loader = DataLoader(input_path)
        dataframe = loader.load()
        job_manager.update_progress_for_user(user_id, job_id, 10.0)

        progress_messages: list[tuple[float, str]] = []

        def progress_callback(progress: float, message: str) -> None:
            clamped = max(10.0, min(95.0, float(progress)))
            job_manager.update_progress_for_user(user_id, job_id, clamped)
            progress_messages.append((clamped, message))

        engine = AnalysisEngine()
        job_parameters = job.get("parameters", {})
        processing_parameters = ProcessingParameters(
            session_id=user_id,
            dataset_name=job_parameters.get("dataset_name"),
            catchment_threshold_area=job_parameters.get("catchment_threshold_area")
            if job_parameters.get("catchment_threshold_area") is not None
            else 1.0,
        )
        model_results = engine.run_analysis(
            csv_data=dataframe,
            parameters=processing_parameters,
            progress_callback=progress_callback,
        )

        csv_path = output_dir / "contributions.csv"
        contributions_df, model_type = ModelRunner.build_contributions_csv(dataframe, csv_path)

        elapsed = perf_counter() - started
        current_params = job.get("parameters", {})
        updated_params = {
            **current_params,
            "sample_count": int(len(contributions_df)),
            "model_type": model_type,
            "processing_time_seconds": round(elapsed, 3),
            "models_run": model_results.get("models_run", []),
        }

        job_manager.update_status_for_user(
            user_id,
            job_id,
            "completed",
            progress_percent=100.0,
            output_dir=output_dir,
            results_csv=csv_path,
            parameters=updated_params,
            error_message=None,
        )
        logger.info("Job %s completed successfully", job_id)

    except Exception as error:
        logger.error("Job %s failed: %s", job_id, traceback.format_exc())
        existing = job_manager.get_job_for_user(user_id, job_id)
        parameters = existing.get("parameters", {}) if existing else {}
        job_manager.update_status_for_user(
            user_id,
            job_id,
            "failed",
            error_message=str(error),
            progress_percent=100.0,
            parameters=parameters,
        )


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )

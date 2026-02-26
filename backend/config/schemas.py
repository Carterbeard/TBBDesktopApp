"""Data validation and API response schemas."""

from datetime import datetime
from typing import Literal, Optional, List

from pydantic import BaseModel, Field


class ProcessingParameters(BaseModel):
    """Parameters for analysis."""

    session_id: str
    dataset_name: Optional[str] = None
    catchment_threshold_area: float = Field(default=1.0, ge=0.1, le=10.0)
    decay_rate: Optional[float] = Field(default=0.01, ge=0.0, le=1.0)
    chemicals_to_analyze: List[str] = Field(default=["NO3"])


class AnalysisStatus(BaseModel):
    """Analysis job status."""

    job_id: str
    status: str
    progress: float = Field(ge=0, le=100)
    current_step: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class UploadResponse(BaseModel):
    """Response after file upload."""

    job_id: str
    status: str
    dataset_name: str
    sample_count: int
    user_id: str
    message: str = "File uploaded successfully"


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    progress_percent: float = 0.0
    error_message: Optional[str] = None
    user_id: str
    created_at: str
    completed_at: Optional[str] = None


class ProcessResponse(BaseModel):
    job_id: str
    status: str
    progress_percent: float = 0.0
    user_id: str
    message: str


class ResultsResponse(BaseModel):
    job_id: str
    user_id: str
    dataset_name: str
    sample_count: int
    csv_file_name: str
    csv_columns: list[str] = Field(default_factory=list)
    rows: list[dict] = Field(default_factory=list)
    summary: dict = Field(default_factory=dict)
    model_type: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str
    job_id: Optional[str] = None


class RegisterRequest(BaseModel):
    email: str = Field(description="Unique account email", examples=["user@example.com"])
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Account password (minimum 8 characters)",
        examples=["Str0ngPass123!"],
    )
    full_name: Optional[str] = Field(default=None, max_length=120, description="Optional display name")


class LoginRequest(BaseModel):
    email: str = Field(description="Registered account email")
    password: str = Field(min_length=8, max_length=128, description="Account password")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(description="Refresh token issued by login/register")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(description="Refresh token to revoke")


class UserProfileResponse(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str] = None
    role: Literal["user", "admin"] = "user"
    is_active: bool = True
    created_at: str
    last_seen_at: str


class TokenPairResponse(BaseModel):
    access_token: str = Field(description="JWT access token for protected APIs")
    refresh_token: str = Field(description="JWT refresh token used to obtain new access tokens")
    token_type: str = Field(default="bearer", description="Authorization scheme")
    expires_in: int = Field(description="Access token expiration in seconds")
    user: UserProfileResponse

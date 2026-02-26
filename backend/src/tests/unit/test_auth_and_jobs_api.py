import io
import sys
import time
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def log(msg: str):
    print(f"[TEST] {msg}", flush=True)


def log_response(label: str, response) -> None:
    try:
        payload = response.json()
        body = json.dumps(payload, indent=2, default=str)
    except Exception:
        body = response.text

    log(f"{label} -> status={response.status_code}\n{body}")


BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import api as api_module
from src.core.auth_service import AuthService
from src.core.job_manager import JobManager


@pytest.fixture
def isolated_client(monkeypatch, tmp_path):
    log("Setting up isolated test client")

    data_dir = tmp_path / "data"
    db_path = data_dir / "jobs.db"
    uploads_dir = data_dir / "uploads"

    data_dir.mkdir(parents=True, exist_ok=True)

    object.__setattr__(api_module.settings, "data_dir", data_dir)
    object.__setattr__(api_module.settings, "jwt_secret", "this-is-a-test-secret-with-at-least-32-bytes")
    object.__setattr__(api_module.settings, "jwt_issuer", "test-issuer")
    object.__setattr__(api_module.settings, "jwt_audience", "test-audience")

    job_manager = JobManager(db_path=db_path, uploads_dir=uploads_dir)
    auth_service = AuthService(job_manager)

    monkeypatch.setattr(api_module, "job_manager", job_manager)
    monkeypatch.setattr(api_module, "auth_service", auth_service)

    client = TestClient(api_module.app)
    log("Isolated API client ready")
    return client, job_manager, auth_service


def _register_and_get_tokens(client: TestClient, email: str, password: str = "Str0ngPass123!", full_name: str = "Test User"):
    log(f"Registering user: {email}")
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
        },
    )
    log_response("POST /auth/register", response)
    assert response.status_code == 200, response.text
    payload = response.json()
    log(f"User registered: {payload['user']['email']}")
    return payload["access_token"], payload["refresh_token"], payload


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_auth_register_login_me_refresh_logout_flow(isolated_client):
    log("Starting auth flow test")

    client, _, _ = isolated_client

    access_token, refresh_token, register_payload = _register_and_get_tokens(
        client,
        email="auth.flow@example.com",
    )

    log("Testing login")
    login_response = client.post(
        "/auth/login",
        json={"email": "auth.flow@example.com", "password": "Str0ngPass123!"},
    )
    log_response("POST /auth/login", login_response)
    assert login_response.status_code == 200

    log("Testing /auth/me")
    me_response = client.get("/auth/me", headers=_auth_headers(login_response.json()["access_token"]))
    log_response("GET /auth/me", me_response)
    assert me_response.status_code == 200

    log("Testing token refresh")
    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )
    log_response("POST /auth/refresh", refresh_response)
    assert refresh_response.status_code == 200

    log("Testing logout")
    logout_response = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_response.json()["refresh_token"]},
        headers=_auth_headers(refresh_response.json()["access_token"]),
    )
    log_response("POST /auth/logout", logout_response)
    assert logout_response.status_code == 200

    log("Auth flow test completed successfully")


def test_admin_endpoint_requires_admin_role(isolated_client):
    log("Starting admin authorization test")

    client, _, auth_service = isolated_client

    user_access, _, _ = _register_and_get_tokens(client, email="normal.user@example.com")

    log("Checking admin endpoint as normal user")
    forbidden = client.get("/admin/users", headers=_auth_headers(user_access))
    log_response("GET /admin/users (non-admin)", forbidden)
    assert forbidden.status_code == 403

    log("Creating admin user")
    admin_user = auth_service.register_user(
        email="admin.user@example.com",
        password="Adm1nPass123!",
        full_name="Admin User",
        role="admin",
    )
    admin_tokens = auth_service.issue_token_pair(admin_user)

    log("Checking admin endpoint as admin")
    allowed = client.get("/admin/users", headers=_auth_headers(admin_tokens["access_token"]))
    log_response("GET /admin/users (admin)", allowed)
    assert allowed.status_code == 200

    log("Admin authorization test completed")


def test_job_status_is_owner_scoped(isolated_client):
    log("Starting job ownership test")

    client, job_manager, _ = isolated_client

    owner_access, _, owner_payload = _register_and_get_tokens(client, email="owner@example.com")
    other_access, _, _ = _register_and_get_tokens(client, email="other@example.com")

    job = job_manager.create_job(user_id=owner_payload["user"]["user_id"], parameters={"dataset_name": "owner-job"})
    log(f"Created job {job['job_id']}")

    owner_status = client.get(f"/status/{job['job_id']}", headers=_auth_headers(owner_access))
    log_response("GET /status/{job_id} (owner)", owner_status)
    assert owner_status.status_code == 200

    other_status = client.get(f"/status/{job['job_id']}", headers=_auth_headers(other_access))
    log_response("GET /status/{job_id} (other user)", other_status)
    assert other_status.status_code == 404

    log("Job ownership test completed")


def test_upload_process_results_export_flow(isolated_client):
    log("Starting full pipeline integration test")

    client, _, _ = isolated_client
    access_token, _, _ = _register_and_get_tokens(client, email="pipeline.user@example.com")
    headers = _auth_headers(access_token)

    log("Uploading CSV file")
    csv_content = (
        "Sample_id,timestamp,Long,Lat,NO3,Temprature,Turbidity,Conductivity\n"
        "S001,2026-02-25T10:00:00Z,-1.234,51.123,5.2,14.1,2.5,180\n"
        "S002,2026-02-25T10:05:00Z,-1.235,51.124,6.1,13.9,2.8,190\n"
        "S003,2026-02-25T10:10:00Z,-1.236,51.125,4.8,14.4,2.2,175\n"
    )

    upload_response = client.post(
        "/upload",
        headers=headers,
        data={"dataset_name": "integration-dataset", "catchment_threshold_area": "1.0"},
        files={"file": ("samples.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    log_response("POST /upload", upload_response)
    assert upload_response.status_code == 200
    job_id = upload_response.json()["job_id"]

    log(f"Processing job {job_id}")
    process_response = client.post(f"/process/{job_id}", headers=headers)
    log_response("POST /process/{job_id}", process_response)
    assert process_response.status_code == 200

    for i in range(30):
        status_response = client.get(f"/status/{job_id}", headers=headers)
        log_response(f"GET /status/{{job_id}} poll={i}", status_response)
        status = status_response.json()
        log(f"Poll {i}: status={status['status']}")
        if status["status"] == "completed":
            break
        time.sleep(0.1)

    log("Fetching results")
    results = client.get(f"/results/{job_id}", headers=headers)
    log_response("GET /results/{job_id}", results)
    assert results.status_code == 200
    results_payload = results.json()

    expected_columns = [
        "Sample_id",
        "timestamp",
        "Long",
        "Lat",
        "NO3",
        "Temprature",
        "Turbidity",
        "Conductivity",
        "nitrate_contribution",
        "conservative_contribution_1",
        "conservative_contribution_2",
        "conservative_contribution_3",
    ]
    assert results_payload["csv_columns"] == expected_columns

    log("Exporting CSV")
    export = client.get(f"/export/{job_id}?format=csv", headers=headers)
    log_response("GET /export/{job_id}?format=csv", export)
    assert export.status_code == 200

    log("Pipeline integration test completed successfully")
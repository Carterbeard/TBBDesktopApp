# OASIS Backend

## Overview

The backend is a standalone FastAPI service used by the desktop frontend.

It currently provides:
- Local user authentication (register, login, refresh, logout)
- Role-aware authorization (`user`, `admin`)
- User-owned analysis jobs (each job belongs to one user)
- CSV upload, validation, processing, progress tracking
- Results retrieval as structured JSON + CSV export

Core behavior:
- One uploaded CSV creates one job
- If both nitrate and conservative tracers exist, processing still returns one consolidated job result
- Result columns include original chemistry columns plus generated contribution columns

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Install

```bash
cd backend
pip install -r requirements.txt
```

### Run API

```bash
python api.py
```

Default URL:
- `http://127.0.0.1:5050`

Interactive docs:
- `http://127.0.0.1:5050/docs`

---

## Configuration

Configuration is environment-driven from `config/settings.py`.

### Common Variables

- `HOST` (default `127.0.0.1`)
- `PORT` (default `5050`)
- `CORS_ORIGINS` (default `*`)
- `DATA_DIR` (default `backend/data`)
- `LOG_LEVEL` (default `INFO`)

### Auth Variables

- `ENVIRONMENT` (`development` by default)
- `JWT_SECRET` (set a strong secret, minimum 32 bytes recommended)
- `JWT_ALGORITHM` (default `HS256`)
- `JWT_ISSUER` (default `oasis-backend`)
- `JWT_AUDIENCE` (default `oasis-desktop`)
- `ACCESS_TOKEN_TTL_MINUTES` (default `30`)
- `REFRESH_TOKEN_TTL_DAYS` (default `14`)

Security check:
- If `ENVIRONMENT != development` and `JWT_SECRET` is weak, startup fails.

---

## Project Structure

```text
backend/
├── api.py
├── requirements.txt
├── config/
│   ├── settings.py
│   ├── schemas.py
│   ├── constants.py
│   └── logging_config.py
├── src/
│   ├── core/
│   │   ├── auth_service.py
│   │   ├── job_manager.py
│   │   ├── data_loader.py
│   │   ├── model_runner.py
│   │   ├── analysis_engine.py
│   │   └── pipeline.py
│   ├── models/
│   │   ├── nitrate/
│   │   └── conservative/
│   └── tests/
│       └── unit/
│           ├── test_models.py
│           └── test_auth_and_jobs_api.py
└── data/
    ├── jobs.db
    ├── uploads/
    └── outputs/
```

---

## Authentication API

### Auth Flow
1. `POST /auth/register` or `POST /auth/login`
2. Store `access_token` + `refresh_token`
3. Send `Authorization: Bearer <access_token>` for protected endpoints
4. Use `POST /auth/refresh` to rotate tokens
5. Use `POST /auth/logout` to revoke refresh session

### Endpoints

#### Register
`POST /auth/register`

Body:
```json
{
  "email": "user@example.com",
  "password": "Str0ngPass123!",
  "full_name": "User Name"
}
```

#### Login
`POST /auth/login`

Body:
```json
{
  "email": "user@example.com",
  "password": "Str0ngPass123!"
}
```

#### Refresh
`POST /auth/refresh`

Body:
```json
{
  "refresh_token": "<token>"
}
```

#### Logout
`POST /auth/logout`

Body:
```json
{
  "refresh_token": "<token>"
}
```

#### Current User
`GET /auth/me`

#### Admin Users (admin role)
`GET /admin/users`

---

## Jobs API

All jobs endpoints require access token.

- `GET /jobs` — list current user jobs
- `POST /upload` — upload CSV and create queued job
- `POST /process/{job_id}` — start background processing
- `GET /status/{job_id}` — status + progress
- `GET /results/{job_id}` — structured JSON results
- `GET /export/{job_id}?format=csv` — download consolidated CSV

### Upload Requirements

Required input columns:
- `Sample_id`
- `timestamp`
- `Long` (or alias normalized to longitude)
- `Lat` (or alias normalized to latitude)

At least one chemistry column is required.

---

## Results Contract

`GET /results/{job_id}` returns:
- `job_id`, `user_id`, `dataset_name`, `sample_count`
- `csv_file_name`
- `csv_columns`
- `rows`
- `summary`
- `model_type`

Expected `csv_columns` shape:

```json
[
  "Sample_id",
  "timestamp",
  "Long",
  "Lat",
  "Temprature",
  "Turbidity",
  "Conductivity",
  "nitrate_contribution",
  "conservative_contribution_1",
  "conservative_contribution_2"
]
```

Rules:
- Original chemistry columns are preserved
- `nitrate_contribution` is added if nitrate/NO3 columns exist
- One conservative contribution column is generated per conservative chemistry input column:
  - `conservative_contribution_1 ... conservative_contribution_n`

---

## Frontend Developer Guide

This section is specifically for frontend integration.

### 1) Base URL
Use backend base URL from environment (default):
- `http://127.0.0.1:5050`

### 2) Store Tokens After Login
After `register`/`login`, persist:
- `access_token` for API calls
- `refresh_token` for token rotation

### 3) Always Send Bearer Token
For protected routes:

```http
Authorization: Bearer <access_token>
```

### 4) Typical UX Sequence
1. User logs in
2. User uploads CSV with `POST /upload`
3. UI receives `job_id`
4. UI starts processing `POST /process/{job_id}`
5. UI polls `GET /status/{job_id}` every 300–800ms
6. When completed, call `GET /results/{job_id}` to render table/chart data
7. Offer download via `GET /export/{job_id}?format=csv`

### 5) Suggested Error Handling
- `401`: token missing/expired → attempt refresh then retry
- `403`: role forbidden (admin routes)
- `404`: job not found or not owned by current user
- `400`: invalid input
- `500`: backend processing failure

### 6) Polling Pattern Example
- Stop polling when `status` is `completed` or `failed`
- If `failed`, show `error_message` from `/status/{job_id}`

### 7) Ownership Model
Jobs are user-scoped:
- A user can only see their own jobs/results/exports
- Never cache another user’s `job_id` across sessions

---

## Testing

Run model tests:

```bash
python -m pytest src/tests/unit/test_models.py -v
```

Run auth + jobs API tests:

```bash
python -m pytest src/tests/unit/test_auth_and_jobs_api.py -v
```

Run all tests:

```bash
python -m pytest src/tests/unit -v
```

---

## Notes

- Backend currently uses SQLite (`data/jobs.db`) for users, jobs, and refresh sessions.
- API docs are the source of truth for request/response schema:
  - `http://127.0.0.1:5050/docs`

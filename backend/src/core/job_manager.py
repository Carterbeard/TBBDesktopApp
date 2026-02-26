import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import settings


VALID_STATUSES = {"queued", "processing", "completed", "failed"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        uploads_dir: Optional[Path] = None,
    ) -> None:
        base_dir = settings.data_dir
        base_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = Path(db_path) if db_path else base_dir / "jobs.db"
        self.uploads_dir = Path(uploads_dir) if uploads_dir else base_dir / "uploads"

        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _table_columns(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}

    def _ensure_column(self, conn: sqlite3.Connection, table_name: str, column_sql: str, column_name: str) -> None:
        columns = self._table_columns(conn, table_name)
        if column_name not in columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    password_hash TEXT,
                    full_name TEXT,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_sessions (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    replaced_by_jti TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    status TEXT NOT NULL,
                    progress_percent REAL NOT NULL DEFAULT 0,
                    error_message TEXT,
                    input_file TEXT,
                    results_csv TEXT,
                    parameters TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    output_dir TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

            self._ensure_column(conn, "jobs", "user_id TEXT", "user_id")
            self._ensure_column(conn, "jobs", "progress_percent REAL NOT NULL DEFAULT 0", "progress_percent")
            self._ensure_column(conn, "jobs", "error_message TEXT", "error_message")
            self._ensure_column(conn, "jobs", "results_csv TEXT", "results_csv")
            self._ensure_column(conn, "users", "password_hash TEXT", "password_hash")
            self._ensure_column(conn, "users", "full_name TEXT", "full_name")
            self._ensure_column(conn, "users", "role TEXT NOT NULL DEFAULT 'user'", "role")
            self._ensure_column(conn, "users", "is_active INTEGER NOT NULL DEFAULT 1", "is_active")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs (user_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs (user_id, status)")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users (email)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_sessions (user_id)")
            conn.commit()

    def _validate_status(self, status: str) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Valid: {sorted(VALID_STATUSES)}")

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        record = dict(row)
        raw_params = record.get("parameters")
        record["parameters"] = json.loads(raw_params) if raw_params else {}
        return record

    def create_user_if_missing(self, user_id: str, email: Optional[str] = None) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT user_id, email, full_name, role, is_active, created_at, last_seen_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE users SET email = COALESCE(?, email), last_seen_at = ? WHERE user_id = ?",
                    (email, now, user_id),
                )
            else:
                conn.execute(
                    "INSERT INTO users (user_id, email, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                    (user_id, email, now, now),
                )

            conn.commit()

            row = conn.execute(
                "SELECT user_id, email, full_name, role, is_active, created_at, last_seen_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else {"user_id": user_id, "email": email}

    def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: Optional[str] = None,
        role: str = "user",
    ) -> dict[str, Any]:
        user_id = str(uuid.uuid4())
        now = _utc_now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, email, password_hash, full_name, role, is_active, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, password_hash, full_name, role, 1, now, now),
            )
            conn.commit()

            row = conn.execute(
                "SELECT user_id, email, full_name, role, is_active, created_at, last_seen_at FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else {}

    def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, email, password_hash, full_name, role, is_active, created_at, last_seen_at
                FROM users WHERE lower(email) = lower(?)
                """,
                (email,),
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id, email, password_hash, full_name, role, is_active, created_at, last_seen_at
                FROM users WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def update_user_last_seen(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET last_seen_at = ? WHERE user_id = ?",
                (_utc_now_iso(), user_id),
            )
            conn.commit()

    def list_users(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_id, email, full_name, role, is_active, created_at, last_seen_at
                FROM users
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def create_refresh_session(self, *, jti: str, user_id: str, expires_at: str) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO refresh_sessions (jti, user_id, expires_at, created_at, revoked_at, replaced_by_jti)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (jti, user_id, expires_at, now, None, None),
            )
            conn.commit()

    def get_refresh_session(self, jti: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT jti, user_id, expires_at, created_at, revoked_at, replaced_by_jti
                FROM refresh_sessions
                WHERE jti = ?
                """,
                (jti,),
            ).fetchone()
            return dict(row) if row else None

    def revoke_refresh_session(self, jti: str, replaced_by_jti: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE refresh_sessions
                SET revoked_at = ?, replaced_by_jti = COALESCE(?, replaced_by_jti)
                WHERE jti = ?
                """,
                (_utc_now_iso(), replaced_by_jti, jti),
            )
            conn.commit()

    def create_job(
        self,
        user_id: str,
        *,
        input_file: Optional[str | Path] = None,
        parameters: Optional[dict[str, Any]] = None,
        output_dir: Optional[str | Path] = None,
        results_csv: Optional[str | Path] = None,
        job_id: Optional[str] = None,
    ) -> dict[str, Any]:
        job_id = job_id or str(uuid.uuid4())
        status = "queued"
        created_at = _utc_now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, user_id, status, progress_percent, error_message,
                    input_file, results_csv, parameters, created_at, completed_at, output_dir
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    user_id,
                    status,
                    0.0,
                    None,
                    str(input_file) if input_file else None,
                    str(results_csv) if results_csv else None,
                    json.dumps(parameters or {}),
                    created_at,
                    None,
                    str(output_dir) if output_dir else None,
                ),
            )
            conn.commit()

        job = self.get_job_for_user(user_id, job_id)
        if not job:
            raise RuntimeError("Job creation failed.")
        return job

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, user_id, status, progress_percent, error_message,
                       input_file, results_csv, parameters, created_at, completed_at, output_dir
                FROM jobs WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def get_job_for_user(self, user_id: str, job_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, user_id, status, progress_percent, error_message,
                       input_file, results_csv, parameters, created_at, completed_at, output_dir
                FROM jobs WHERE job_id = ? AND user_id = ?
                """,
                (job_id, user_id),
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def update_status_for_user(
        self,
        user_id: str,
        job_id: str,
        status: str,
        *,
        progress_percent: Optional[float] = None,
        error_message: Optional[str] = None,
        input_file: Optional[str | Path] = None,
        parameters: Optional[dict[str, Any]] = None,
        output_dir: Optional[str | Path] = None,
        results_csv: Optional[str | Path] = None,
        completed_at: Optional[str] = None,
    ) -> dict[str, Any]:
        self._validate_status(status)

        existing = self.get_job_for_user(user_id, job_id)
        if not existing:
            raise KeyError(f"Job '{job_id}' not found for user '{user_id}'.")

        final_completed_at = completed_at
        if status in {"completed", "failed"} and not final_completed_at:
            final_completed_at = _utc_now_iso()
        if status in {"queued", "processing"}:
            final_completed_at = None

        if progress_percent is None:
            if status == "completed":
                progress_percent = 100.0
            elif status in {"queued", "failed"}:
                progress_percent = existing.get("progress_percent", 0.0)
            else:
                progress_percent = existing.get("progress_percent", 0.0)

        new_input_file = str(input_file) if input_file is not None else existing["input_file"]
        new_output_dir = str(output_dir) if output_dir is not None else existing["output_dir"]
        new_results_csv = str(results_csv) if results_csv is not None else existing.get("results_csv")
        new_parameters = parameters if parameters is not None else existing.get("parameters", {})
        new_error = error_message if error_message is not None else existing.get("error_message")

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, progress_percent = ?, error_message = ?, input_file = ?,
                    results_csv = ?, parameters = ?, completed_at = ?, output_dir = ?
                WHERE job_id = ? AND user_id = ?
                """,
                (
                    status,
                    float(progress_percent),
                    new_error,
                    new_input_file,
                    new_results_csv,
                    json.dumps(new_parameters or {}),
                    final_completed_at,
                    new_output_dir,
                    job_id,
                    user_id,
                ),
            )
            conn.commit()

        job = self.get_job_for_user(user_id, job_id)
        if not job:
            raise RuntimeError("Job update failed.")
        return job

    def update_progress_for_user(self, user_id: str, job_id: str, progress_percent: float) -> dict[str, Any]:
        existing = self.get_job_for_user(user_id, job_id)
        if not existing:
            raise KeyError(f"Job '{job_id}' not found for user '{user_id}'.")

        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET progress_percent = ? WHERE job_id = ? AND user_id = ?",
                (float(progress_percent), job_id, user_id),
            )
            conn.commit()

        job = self.get_job_for_user(user_id, job_id)
        if not job:
            raise RuntimeError("Progress update failed.")
        return job

    def list_jobs_for_user(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None:
            self._validate_status(status)

        query = """
            SELECT job_id, user_id, status, progress_percent, error_message,
                   input_file, results_csv, parameters, created_at, completed_at, output_dir
            FROM jobs
            WHERE user_id = ?
        """
        params: list[Any] = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def get_upload_path(self, user_id: str, job_id: str, original_filename: str) -> Path:
        ext = Path(original_filename).suffix or ".csv"
        return self.uploads_dir / user_id / job_id / f"input{ext}"

    def save_upload(self, user_id: str, job_id: str, original_filename: str, content: bytes) -> Path:
        path = self.get_upload_path(user_id, job_id, original_filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

        self.update_status_for_user(user_id, job_id, status="queued", input_file=path)
        return path

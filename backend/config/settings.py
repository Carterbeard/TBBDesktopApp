"""Application settings."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


def _parse_cors_origins(value: str | None) -> List[str]:
    if not value:
        return ["*"]

    raw = value.strip()
    if raw == "*":
        return ["*"]

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    cors_origins: List[str]
    data_dir: Path
    log_level: str
    api_prefix: str
    max_upload_size: int
    allowed_extensions: set[str]
    default_catchment_threshold: float
    default_decay_rate: float
    environment: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_issuer: str
    jwt_audience: str
    access_token_ttl_minutes: int
    refresh_token_ttl_days: int

    @property
    def BASE_DIR(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def DATA_DIR(self) -> Path:
        return self.data_dir

    @property
    def UPLOAD_DIR(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def OUTPUT_DIR(self) -> Path:
        return self.BASE_DIR / "outputs"

    @property
    def LOG_DIR(self) -> Path:
        return self.BASE_DIR / "logs"

    @property
    def NITRATE_MODEL_OUTPUT_DIR(self) -> Path:
        return self.BASE_DIR / "nitrate_model_outputs"

    @property
    def CONSERVATIVE_MODEL_OUTPUT_DIR(self) -> Path:
        return self.BASE_DIR / "conservative_model_outputs"

    @classmethod
    def from_env(cls) -> "Settings":
        backend_root = Path(__file__).resolve().parents[1]
        default_data_dir = backend_root / "data"

        host = os.getenv("HOST", os.getenv("API_HOST", "127.0.0.1"))
        port = int(os.getenv("PORT", os.getenv("API_PORT", "5050")))
        cors_origins = _parse_cors_origins(os.getenv("CORS_ORIGINS", "*"))
        data_dir = Path(os.getenv("DATA_DIR", str(default_data_dir))).expanduser().resolve()
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        api_prefix = os.getenv("API_PREFIX", "/api/v1")
        max_upload_size = int(os.getenv("MAX_UPLOAD_SIZE", str(100 * 1024 * 1024)))
        default_catchment_threshold = float(os.getenv("DEFAULT_CATCHMENT_THRESHOLD", "1.0"))
        default_decay_rate = float(os.getenv("DEFAULT_DECAY_RATE", "0.01"))
        environment = os.getenv("ENVIRONMENT", "development").lower()
        jwt_secret = os.getenv("JWT_SECRET", "dev-secret-change-me")
        jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        jwt_issuer = os.getenv("JWT_ISSUER", "oasis-backend")
        jwt_audience = os.getenv("JWT_AUDIENCE", "oasis-desktop")
        access_token_ttl_minutes = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES", "30"))
        refresh_token_ttl_days = int(os.getenv("REFRESH_TOKEN_TTL_DAYS", "14"))

        allowed_extensions_raw = os.getenv("ALLOWED_EXTENSIONS", ".csv,.json,.txt")
        allowed_extensions = {
            ext.strip().lower() if ext.strip().startswith(".") else f".{ext.strip().lower()}"
            for ext in allowed_extensions_raw.split(",")
            if ext.strip()
        }

        return cls(
            host=host,
            port=port,
            cors_origins=cors_origins,
            data_dir=data_dir,
            log_level=log_level,
            api_prefix=api_prefix,
            max_upload_size=max_upload_size,
            allowed_extensions=allowed_extensions,
            default_catchment_threshold=default_catchment_threshold,
            default_decay_rate=default_decay_rate,
            environment=environment,
            jwt_secret=jwt_secret,
            jwt_algorithm=jwt_algorithm,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            access_token_ttl_minutes=access_token_ttl_minutes,
            refresh_token_ttl_days=refresh_token_ttl_days,
        )


settings = Settings.from_env()

# Backward-compatible module-level names
BASE_DIR = settings.BASE_DIR
DATA_DIR = settings.DATA_DIR
UPLOAD_DIR = settings.UPLOAD_DIR
OUTPUT_DIR = settings.OUTPUT_DIR
LOG_DIR = settings.LOG_DIR
NITRATE_MODEL_OUTPUT_DIR = settings.NITRATE_MODEL_OUTPUT_DIR
CONSERVATIVE_MODEL_OUTPUT_DIR = settings.CONSERVATIVE_MODEL_OUTPUT_DIR
API_HOST = settings.host
API_PORT = settings.port
API_PREFIX = settings.api_prefix
MAX_UPLOAD_SIZE = settings.max_upload_size
ALLOWED_EXTENSIONS = settings.allowed_extensions
DEFAULT_CATCHMENT_THRESHOLD = settings.default_catchment_threshold
DEFAULT_DECAY_RATE = settings.default_decay_rate
LOG_LEVEL = settings.log_level
ENVIRONMENT = settings.environment
JWT_SECRET = settings.jwt_secret
JWT_ALGORITHM = settings.jwt_algorithm
JWT_ISSUER = settings.jwt_issuer
JWT_AUDIENCE = settings.jwt_audience
ACCESS_TOKEN_TTL_MINUTES = settings.access_token_ttl_minutes
REFRESH_TOKEN_TTL_DAYS = settings.refresh_token_ttl_days

# Ensure runtime directories exist
for directory in [
    DATA_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    LOG_DIR,
    NITRATE_MODEL_OUTPUT_DIR,
    CONSERVATIVE_MODEL_OUTPUT_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)

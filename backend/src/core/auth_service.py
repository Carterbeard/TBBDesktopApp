import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from passlib.context import CryptContext

from config.settings import settings
from src.core.job_manager import JobManager


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(value: datetime) -> str:
    return value.isoformat()


class AuthService:
    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager

    def _build_claims(self, *, user: dict[str, Any], token_type: str, jti: str, expires_at: datetime) -> dict[str, Any]:
        now = _utc_now()
        return {
            "sub": user["user_id"],
            "email": user["email"],
            "role": user.get("role", "user"),
            "token_type": token_type,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }

    def _encode(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    def _decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )

    def register_user(self, *, email: str, password: str, full_name: Optional[str] = None, role: str = "user") -> dict[str, Any]:
        existing = self.job_manager.get_user_by_email(email)
        if existing:
            raise ValueError("An account with this email already exists")

        password_hash = pwd_context.hash(password)
        user = self.job_manager.create_user(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
        )
        return user

    def authenticate_user(self, *, email: str, password: str) -> dict[str, Any]:
        user = self.job_manager.get_user_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")

        if not user.get("is_active", 1):
            raise ValueError("Account is disabled")

        password_hash = user.get("password_hash")
        if not password_hash or not pwd_context.verify(password, password_hash):
            raise ValueError("Invalid email or password")

        self.job_manager.update_user_last_seen(user["user_id"])
        refreshed = self.job_manager.get_user_by_id(user["user_id"])
        return refreshed or user

    def issue_token_pair(self, user: dict[str, Any]) -> dict[str, Any]:
        now = _utc_now()
        access_exp = now + timedelta(minutes=settings.access_token_ttl_minutes)
        refresh_exp = now + timedelta(days=settings.refresh_token_ttl_days)

        access_jti = str(uuid.uuid4())
        refresh_jti = str(uuid.uuid4())

        access_claims = self._build_claims(
            user=user,
            token_type="access",
            jti=access_jti,
            expires_at=access_exp,
        )
        refresh_claims = self._build_claims(
            user=user,
            token_type="refresh",
            jti=refresh_jti,
            expires_at=refresh_exp,
        )

        refresh_token = self._encode(refresh_claims)
        self.job_manager.create_refresh_session(
            jti=refresh_jti,
            user_id=user["user_id"],
            expires_at=_to_iso(refresh_exp),
        )

        return {
            "access_token": self._encode(access_claims),
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_ttl_minutes * 60,
        }

    def verify_access_token(self, token: str) -> dict[str, Any]:
        claims = self._decode(token)
        if claims.get("token_type") != "access":
            raise ValueError("Invalid token type")

        user_id = str(claims.get("sub") or "").strip()
        if not user_id:
            raise ValueError("Token missing subject")

        user = self.job_manager.get_user_by_id(user_id)
        if not user or not user.get("is_active", 1):
            raise ValueError("User is not active")

        return {
            "user_id": user_id,
            "email": user.get("email"),
            "role": user.get("role", "user"),
        }

    def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        claims = self._decode(refresh_token)
        if claims.get("token_type") != "refresh":
            raise ValueError("Invalid token type")

        jti = claims.get("jti")
        if not jti:
            raise ValueError("Refresh token missing jti")

        session = self.job_manager.get_refresh_session(jti)
        if not session:
            raise ValueError("Refresh session not found")

        if session.get("revoked_at"):
            raise ValueError("Refresh token revoked")

        expires_at = session.get("expires_at")
        if expires_at and datetime.fromisoformat(expires_at) <= _utc_now():
            raise ValueError("Refresh token expired")

        user = self.job_manager.get_user_by_id(session["user_id"])
        if not user or not user.get("is_active", 1):
            raise ValueError("User is not active")

        new_tokens = self.issue_token_pair(user)
        new_claims = self._decode(new_tokens["refresh_token"])
        self.job_manager.revoke_refresh_session(jti, replaced_by_jti=new_claims.get("jti"))
        return new_tokens

    def revoke_refresh_token(self, refresh_token: str) -> None:
        claims = self._decode(refresh_token)
        if claims.get("token_type") != "refresh":
            raise ValueError("Invalid token type")

        jti = claims.get("jti")
        if not jti:
            raise ValueError("Refresh token missing jti")

        self.job_manager.revoke_refresh_session(jti)

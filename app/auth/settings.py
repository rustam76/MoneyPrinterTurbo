"""Auth configuration from environment variables only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from loguru import logger

_AUTH_DISABLED_WARNED = False


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    database_url: str
    session_secret: str
    session_expire_hours: int
    cookie_secure: bool
    public_api_url: str
    public_webui_url: str
    cookie_name: str = "MPT_SESSION"
    csrf_header: str = "X-CSRF-Token"
    login_max_failures: int = 5
    login_window_seconds: int = 15 * 60


@lru_cache(maxsize=1)
def auth_settings() -> AuthSettings:
    return AuthSettings(
        enabled=_env_bool("MPT_AUTH_ENABLED", default=False),
        database_url=(os.getenv("DATABASE_URL") or "").strip(),
        session_secret=(os.getenv("MPT_SESSION_SECRET") or "").strip(),
        session_expire_hours=max(1, _env_int("MPT_SESSION_EXPIRE_HOURS", 24)),
        cookie_secure=_env_bool("MPT_COOKIE_SECURE", default=False),
        public_api_url=(os.getenv("MPT_PUBLIC_API_URL") or "").rstrip("/"),
        public_webui_url=(os.getenv("MPT_PUBLIC_WEBUI_URL") or "").rstrip("/"),
    )


def is_auth_enabled() -> bool:
    global _AUTH_DISABLED_WARNED
    settings = auth_settings()
    if not settings.enabled and not _AUTH_DISABLED_WARNED:
        logger.warning("WARNING: Authentication is disabled.")
        _AUTH_DISABLED_WARNED = True
    return settings.enabled


def mask_database_url(url: str) -> str:
    """Mask password in a SQLAlchemy/Postgres URL for safe logging."""
    if not url:
        return ""
    try:
        # postgresql://user:pass@host/db → postgresql://user:****@host/db
        if "://" not in url:
            return url
        scheme, rest = url.split("://", 1)
        if "@" not in rest or ":" not in rest.split("@", 1)[0]:
            return url
        creds, hostpart = rest.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:****@{hostpart}"
    except Exception:
        return "****"


def require_auth_config() -> AuthSettings:
    settings = auth_settings()
    if not settings.enabled:
        return settings
    if not settings.database_url:
        raise RuntimeError("Authentication database is not configured.")
    if not settings.session_secret or settings.session_secret == (
        "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"
    ):
        raise RuntimeError(
            "MPT_SESSION_SECRET must be set to a long random value when auth is enabled."
        )
    return settings

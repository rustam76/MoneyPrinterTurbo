"""Opaque session tokens and one-time establish codes."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from uuid import uuid4


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_establish_code() -> str:
    return secrets.token_urlsafe(24)


def sign_value(secret: str, value: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{value}.{digest}"


def verify_signed_value(secret: str, signed: str) -> str | None:
    if not signed or "." not in signed:
        return None
    value, _, signature = signed.rpartition(".")
    expected = hmac.new(
        secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return value


def new_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def new_user_id() -> str:
    return str(uuid4())

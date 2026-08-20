"""Cookie helpers for auth sessions."""

from __future__ import annotations

from fastapi import Response

from app.auth.settings import auth_settings


def set_session_cookie(response: Response, raw_token: str, *, secure: bool | None = None) -> None:
    settings = auth_settings()
    use_secure = settings.cookie_secure if secure is None else secure
    max_age = settings.session_expire_hours * 3600
    response.set_cookie(
        key=settings.cookie_name,
        value=raw_token,
        max_age=max_age,
        httponly=True,
        secure=use_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    settings = auth_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        samesite="lax",
    )


def read_session_token_from_cookie(cookies: dict) -> str | None:
    settings = auth_settings()
    value = cookies.get(settings.cookie_name)
    if not value:
        return None
    return str(value)

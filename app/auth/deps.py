"""FastAPI dependencies for authentication."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.cookies import read_session_token_from_cookie
from app.auth.db import db_session
from app.auth.errors import AuthForbiddenError, AuthUnauthorizedError
from app.auth.models import AuthSession, User, UserRole
from app.auth.service import resolve_session
from app.auth.settings import is_auth_enabled


def get_raw_session_token(request: Request) -> str | None:
    return read_session_token_from_cookie(request.cookies)


def get_current_user_optional(
    request: Request,
    db: Annotated[Session, Depends(db_session)],
) -> tuple[User, AuthSession] | None:
    if not is_auth_enabled():
        return None
    return resolve_session(db, get_raw_session_token(request))


def get_current_user(
    pair: Annotated[
        tuple[User, AuthSession] | None, Depends(get_current_user_optional)
    ],
) -> tuple[User, AuthSession]:
    if pair is None:
        raise AuthUnauthorizedError("Authentication required.")
    return pair


def require_admin(
    pair: Annotated[tuple[User, AuthSession], Depends(get_current_user)],
) -> tuple[User, AuthSession]:
    user, session = pair
    if user.role != UserRole.admin:
        raise AuthForbiddenError()
    return user, session

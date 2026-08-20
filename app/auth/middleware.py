"""Protect FastAPI routes when authentication is enabled."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.cookies import read_session_token_from_cookie
from app.auth.db import session_scope
from app.auth.errors import AuthError
from app.auth.service import resolve_session
from app.auth.settings import is_auth_enabled
from app.utils import utils

_PUBLIC_PREFIXES = (
    "/auth/login",
    "/auth/setup",
    "/auth/status",
    "/auth/establish",
    "/docs",
    "/redoc",
    "/openapi.json",
)

_PROTECTED_PREFIXES = (
    "/api/",
    "/tasks",
    "/users",
    "/auth/me",
    "/auth/logout",
    "/auth/csrf",
)

_CSRF_EXEMPT = {
    "/auth/login",
    "/auth/setup",
    "/auth/establish",
    "/auth/logout",
}


def _is_public(path: str) -> bool:
    if path in {"/", "/favicon.ico"}:
        return True
    for prefix in _PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def _needs_auth(path: str) -> bool:
    if _is_public(path):
        return False
    for prefix in _PROTECTED_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if not is_auth_enabled():
            return await call_next(request)

        path = request.url.path
        if not _needs_auth(path):
            return await call_next(request)

        try:
            with session_scope() as db:
                token = read_session_token_from_cookie(request.cookies)
                resolved = resolve_session(db, token)
                if resolved is None:
                    return JSONResponse(
                        status_code=401,
                        content=utils.get_response(
                            401, None, "Authentication required."
                        ),
                    )
                user, session = resolved
                request.state.auth_user = user
                request.state.auth_session = session

                method = request.method.upper()
                if method in {"POST", "PUT", "PATCH", "DELETE"} and path not in _CSRF_EXEMPT:
                    csrf_header = request.headers.get("x-csrf-token", "")
                    if not csrf_header or csrf_header != session.csrf_token:
                        return JSONResponse(
                            status_code=403,
                            content=utils.get_response(
                                403,
                                None,
                                "You don't have permission to perform this action.",
                            ),
                        )
                # Keep session dirty fields (last_activity) by committing via scope
                db.add(session)
        except AuthError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content=utils.get_response(exc.status_code, None, exc.message),
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content=utils.get_response(
                    503, None, "Authentication service temporarily unavailable."
                ),
            )

        return await call_next(request)

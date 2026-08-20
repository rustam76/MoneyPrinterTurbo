"""Auth HTTP controllers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.auth.cookies import clear_session_cookie, set_session_cookie
from app.auth.db import db_session, session_scope
from app.auth.deps import get_current_user, get_raw_session_token
from app.auth.errors import AuthError
from app.auth.schemas import AuthStatusResponse, LoginRequest, SetupRequest, UserPublic
from app.auth.settings import auth_settings, is_auth_enabled
from app.utils import utils

router = APIRouter(tags=["Auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=utils.get_response(exc.status_code, None, exc.message),
    )


def _wants_secure_cookie(request: Request) -> bool:
    settings = auth_settings()
    if settings.cookie_secure:
        return True
    proto = request.headers.get("x-forwarded-proto", "").lower()
    return proto == "https" or request.url.scheme == "https"


@router.get("/auth/status")
def auth_status():
    enabled = is_auth_enabled()
    setup = False
    if enabled:
        try:
            with session_scope() as db:
                setup = auth_service.setup_required(db)
        except Exception as exc:
            raise AuthError(
                "Authentication service temporarily unavailable.", status_code=503
            ) from exc
    payload = AuthStatusResponse(enabled=enabled, setup_required=setup)
    return utils.get_response(200, payload.model_dump())


@router.post("/auth/setup")
def auth_setup(
    body: SetupRequest,
    request: Request,
    db: Annotated[Session, Depends(db_session)],
):
    if not is_auth_enabled():
        return _error_response(AuthError("Authentication is disabled.", status_code=403))
    try:
        user, raw_token, establish_code = auth_service.create_initial_admin(
            db,
            username=body.username,
            email=str(body.email),
            password=body.password,
            confirm_password=body.confirm_password,
        )
    except AuthError as exc:
        return _error_response(exc)

    response = JSONResponse(
        content=utils.get_response(
            200,
            {
                "user": user,
                "establish_code": establish_code,
            },
            "Administrator created.",
        )
    )
    set_session_cookie(response, raw_token, secure=_wants_secure_cookie(request))
    return response


@router.post("/auth/login")
def auth_login(
    body: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(db_session)],
):
    if not is_auth_enabled():
        return _error_response(AuthError("Authentication is disabled.", status_code=403))
    try:
        user, raw_token, establish_code = auth_service.authenticate(
            db,
            username_or_email=body.username_or_email,
            password=body.password,
            client_ip=_client_ip(request),
        )
    except AuthError as exc:
        return _error_response(exc)

    response = JSONResponse(
        content=utils.get_response(
            200,
            {"user": user, "establish_code": establish_code},
            "Login success.",
        )
    )
    set_session_cookie(response, raw_token, secure=_wants_secure_cookie(request))
    return response


@router.post("/auth/logout")
def auth_logout(request: Request):
    if is_auth_enabled():
        token = get_raw_session_token(request)
        try:
            with session_scope() as db:
                auth_service.logout(db, token)
        except Exception:
            pass
    response = JSONResponse(content=utils.get_response(200, None, "Logged out."))
    clear_session_cookie(response)
    return response


@router.get("/auth/me")
def auth_me(
    pair: Annotated[tuple, Depends(get_current_user)],
):
    user, _session = pair
    public = UserPublic.model_validate(auth_service._to_public(user))
    return utils.get_response(200, public.model_dump())


@router.get("/auth/csrf")
def auth_csrf(pair: Annotated[tuple, Depends(get_current_user)]):
    _user, session = pair
    return utils.get_response(200, {"csrf_token": session.csrf_token})


@router.get("/auth/establish")
def auth_establish(
    code: str,
    request: Request,
    db: Annotated[Session, Depends(db_session)],
    next: str = "/",
):
    """Exchange signed establish code for HttpOnly cookie (Streamlit bridge)."""
    settings = auth_settings()
    login_fallback = (
        f"{settings.public_webui_url}/Login" if settings.public_webui_url else "/"
    )
    if not is_auth_enabled():
        target = next if next.startswith("/") else "/"
        return RedirectResponse(url=target, status_code=302)
    raw_token = auth_service.parse_establish_code(code)
    if not raw_token or auth_service.resolve_session(db, raw_token) is None:
        return RedirectResponse(url=login_fallback, status_code=302)

    if not next.startswith("/"):
        next = "/"
    redirect_to = next
    if settings.public_webui_url and next == "/":
        redirect_to = settings.public_webui_url
    elif settings.public_webui_url and next.startswith("/"):
        redirect_to = f"{settings.public_webui_url}{next}"

    response = RedirectResponse(url=redirect_to, status_code=302)
    set_session_cookie(response, raw_token, secure=_wants_secure_cookie(request))
    return response

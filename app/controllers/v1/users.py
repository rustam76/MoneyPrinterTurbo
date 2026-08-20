"""Admin user management API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.auth.db import db_session
from app.auth.deps import require_admin
from app.auth.errors import AuthError
from app.auth.schemas import (
    CreateUserRequest,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserPublic,
)
from app.utils import utils

router = APIRouter(prefix="/users", tags=["Users"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=utils.get_response(exc.status_code, None, exc.message),
    )


@router.get("")
def list_users(
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    _actor, _ = pair
    users = [UserPublic.model_validate(u).model_dump() for u in auth_service.list_users(db)]
    return utils.get_response(200, users)


@router.post("")
def create_user(
    body: CreateUserRequest,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    _actor, _ = pair
    try:
        user = auth_service.create_user(
            db,
            username=body.username,
            email=str(body.email),
            password=body.password,
            role=body.role,
            is_active=body.is_active,
        )
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())


@router.get("/{user_id}")
def get_user(
    user_id: str,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    _actor, _ = pair
    try:
        user = auth_service.get_user(db, user_id)
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())


@router.put("/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserRequest,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    actor, _ = pair
    try:
        user = auth_service.update_user(
            db,
            user_id=user_id,
            actor_id=actor.id,
            username=body.username,
            email=str(body.email) if body.email else None,
            role=body.role,
            is_active=body.is_active,
            password=body.password,
        )
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    actor, _ = pair
    try:
        auth_service.delete_user(db, user_id=user_id, actor_id=actor.id)
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, None, "User deleted.")


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    _actor, _ = pair
    try:
        user = auth_service.reset_password(db, user_id=user_id, password=body.password)
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())


@router.post("/{user_id}/activate")
def activate_user(
    user_id: str,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    actor, _ = pair
    try:
        user = auth_service.set_user_active(
            db, user_id=user_id, actor_id=actor.id, is_active=True
        )
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())


@router.post("/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    pair: Annotated[tuple, Depends(require_admin)],
    db: Annotated[Session, Depends(db_session)],
):
    actor, _ = pair
    try:
        user = auth_service.set_user_active(
            db, user_id=user_id, actor_id=actor.id, is_active=False
        )
    except AuthError as exc:
        return _error_response(exc)
    return utils.get_response(200, UserPublic.model_validate(user).model_dump())

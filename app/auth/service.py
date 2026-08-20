"""Authentication business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from email_validator import EmailNotValidError, validate_email
from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.auth.errors import (
    AuthConflictError,
    AuthError,
    AuthForbiddenError,
    AuthRateLimitError,
    AuthUnauthorizedError,
)
from app.auth.models import AuthSession, User, UserRole, utcnow
from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import login_rate_limiter
from app.auth.settings import auth_settings
from app.auth.tokens import (
    generate_session_token,
    hash_token,
    new_csrf_token,
    new_user_id,
    sign_value,
    verify_signed_value,
)

GENERIC_LOGIN_FAILURE = "Username/email atau password salah."


def user_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User)) or 0)


def setup_required(db: Session) -> bool:
    return user_count(db) == 0


def _normalize_email(email: str) -> str:
    try:
        return validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise AuthError("Email is invalid.", status_code=400) from exc


def _session_expiry() -> datetime:
    hours = auth_settings().session_expire_hours
    return utcnow() + timedelta(hours=hours)


def _to_public(user: User) -> dict:
    def _iso(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
        "is_active": user.is_active,
        "last_login_at": _iso(user.last_login_at),
        "created_at": _iso(user.created_at),
        "updated_at": _iso(user.updated_at),
    }


def _make_establish_code(raw_token: str) -> str:
    secret = auth_settings().session_secret
    expires = int((utcnow() + timedelta(minutes=2)).timestamp())
    return sign_value(secret, f"{raw_token}:{expires}")


def parse_establish_code(code: str) -> str | None:
    secret = auth_settings().session_secret
    payload = verify_signed_value(secret, code)
    if not payload or ":" not in payload:
        return None
    raw_token, _, expires_s = payload.rpartition(":")
    try:
        expires = int(expires_s)
    except ValueError:
        return None
    if expires < int(utcnow().timestamp()):
        return None
    return raw_token


def _create_session_for_user(db: Session, user: User) -> tuple[str, str]:
    raw_token = generate_session_token()
    session = AuthSession(
        id=new_user_id(),
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=new_csrf_token(),
        expires_at=_session_expiry(),
        created_at=utcnow(),
        last_activity_at=utcnow(),
    )
    db.add(session)
    db.flush()
    return raw_token, _make_establish_code(raw_token)


def create_initial_admin(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    confirm_password: str,
) -> tuple[dict, str, str]:
    if password != confirm_password:
        raise AuthError("Passwords do not match.", status_code=400)
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.", status_code=400)

    username = username.strip()
    email = _normalize_email(email)

    if user_count(db) > 0:
        raise AuthForbiddenError("Initial setup is disabled.")

    user = User(
        id=new_user_id(),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.admin,
        is_active=True,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise AuthForbiddenError("Initial setup is disabled.") from exc

    if user_count(db) > 1:
        raise AuthForbiddenError("Initial setup is disabled.")

    raw_token, establish_code = _create_session_for_user(db, user)
    logger.info("Initial administrator created username={}", username)
    return _to_public(user), raw_token, establish_code


def authenticate(
    db: Session,
    *,
    username_or_email: str,
    password: str,
    client_ip: str,
) -> tuple[dict, str, str]:
    identifier = username_or_email.strip()
    if login_rate_limiter.is_blocked(client_ip, identifier):
        raise AuthRateLimitError()

    user = db.scalar(
        select(User).where(
            or_(User.username == identifier, func.lower(User.email) == identifier.lower())
        )
    )
    if (
        user is None
        or not user.is_active
        or not verify_password(user.password_hash, password)
    ):
        login_rate_limiter.record_failure(client_ip, identifier)
        logger.info("Login failed")
        raise AuthUnauthorizedError(GENERIC_LOGIN_FAILURE)

    login_rate_limiter.clear(client_ip, identifier)
    user.last_login_at = utcnow()
    user.updated_at = utcnow()
    raw_token, establish_code = _create_session_for_user(db, user)
    cleanup_expired_sessions(db)
    logger.info("Login success user_id={}", user.id)
    return _to_public(user), raw_token, establish_code


def resolve_session(
    db: Session, raw_token: str | None
) -> tuple[User, AuthSession] | None:
    if not raw_token:
        return None
    session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_token(raw_token))
    )
    if session is None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < utcnow():
        db.delete(session)
        return None
    if not session.user or not session.user.is_active:
        return None
    session.last_activity_at = utcnow()
    return session.user, session


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_token(raw_token))
    )
    if session:
        sid = session.id
        db.delete(session)
        logger.info("Logout session_id={}", sid)


def invalidate_user_sessions(db: Session, user_id: str) -> None:
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user_id)).all()
    for session in sessions:
        db.delete(session)


def cleanup_expired_sessions(db: Session) -> int:
    now = utcnow()
    sessions = db.scalars(select(AuthSession).where(AuthSession.expires_at < now)).all()
    for session in sessions:
        db.delete(session)
    return len(sessions)


def _active_admin_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.is_active.is_(True))
        )
        or 0
    )


def list_users(db: Session) -> list[dict]:
    users = db.scalars(select(User).order_by(User.created_at.asc())).all()
    return [_to_public(u) for u in users]


def get_user(db: Session, user_id: str) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise AuthError("User not found.", status_code=404)
    return _to_public(user)


def create_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    role: str = "user",
    is_active: bool = True,
) -> dict:
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.", status_code=400)
    username = username.strip()
    email = _normalize_email(email)
    role_enum = UserRole(role)
    user = User(
        id=new_user_id(),
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role_enum,
        is_active=is_active,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise AuthConflictError("Username or email already exists.") from exc
    logger.info("User created user_id={} role={}", user.id, role)
    return _to_public(user)


def update_user(
    db: Session,
    *,
    user_id: str,
    actor_id: str,
    username: str | None = None,
    email: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    password: str | None = None,
) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise AuthError("User not found.", status_code=404)

    becoming_inactive = is_active is False and user.is_active
    demoting_admin = (
        role == UserRole.user.value
        and user.role == UserRole.admin
        and user.is_active
    )

    if user_id == actor_id and becoming_inactive:
        raise AuthForbiddenError("You cannot deactivate yourself.")

    if (becoming_inactive or demoting_admin) and user.role == UserRole.admin:
        if _active_admin_count(db) <= 1:
            raise AuthForbiddenError("Cannot remove the last active administrator.")

    if username is not None:
        user.username = username.strip()
    if email is not None:
        user.email = _normalize_email(email)
    if role is not None:
        user.role = UserRole(role)
    if is_active is not None:
        user.is_active = is_active
    if password:
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters.", status_code=400)
        user.password_hash = hash_password(password)
    user.updated_at = utcnow()

    try:
        db.flush()
    except IntegrityError as exc:
        raise AuthConflictError("Username or email already exists.") from exc

    if becoming_inactive or password:
        invalidate_user_sessions(db, user.id)

    logger.info("User updated user_id={}", user.id)
    return _to_public(user)


def reset_password(db: Session, *, user_id: str, password: str) -> dict:
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.", status_code=400)
    user = db.get(User, user_id)
    if not user:
        raise AuthError("User not found.", status_code=404)
    user.password_hash = hash_password(password)
    user.updated_at = utcnow()
    invalidate_user_sessions(db, user.id)
    logger.info("Password reset user_id={}", user.id)
    return _to_public(user)


def set_user_active(
    db: Session, *, user_id: str, actor_id: str, is_active: bool
) -> dict:
    return update_user(
        db, user_id=user_id, actor_id=actor_id, is_active=is_active
    )


def delete_user(db: Session, *, user_id: str, actor_id: str) -> None:
    if user_id == actor_id:
        raise AuthForbiddenError("You cannot delete yourself.")
    user = db.get(User, user_id)
    if not user:
        raise AuthError("User not found.", status_code=404)
    if user.role == UserRole.admin and user.is_active and _active_admin_count(db) <= 1:
        raise AuthForbiddenError("Cannot delete the last active administrator.")
    db.delete(user)
    logger.info("User deleted user_id={}", user_id)

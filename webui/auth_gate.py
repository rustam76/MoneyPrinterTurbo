"""Streamlit authentication gate helpers."""

from __future__ import annotations

from urllib.parse import urlencode

import streamlit as st

from app.auth.cookies import read_session_token_from_cookie
from app.auth.db import session_scope
from app.auth.migrate import run_auth_migrations
from app.auth.models import UserRole
from app.auth import service as auth_service
from app.auth.settings import auth_settings, is_auth_enabled


def _browser_cookies() -> dict:
    try:
        cookies = st.context.cookies
        return dict(cookies) if cookies is not None else {}
    except Exception:
        return {}


def establish_redirect_url(establish_code: str, next_path: str = "/") -> str:
    settings = auth_settings()
    query = urlencode({"code": establish_code, "next": next_path})
    if settings.public_api_url:
        return f"{settings.public_api_url}/auth/establish?{query}"
    return f"/auth/establish?{query}"


def get_authenticated_user():
    """Return public user dict or None. Runs migration lazily when auth enabled."""
    if not is_auth_enabled():
        return None
    run_auth_migrations()
    token = read_session_token_from_cookie(_browser_cookies())
    # Also allow Streamlit session_state bridge for same-process UX before cookie lands
    if not token:
        token = st.session_state.get("_mpt_session_token")
    if not token:
        return None
    with session_scope() as db:
        resolved = auth_service.resolve_session(db, token)
        if not resolved:
            st.session_state.pop("_mpt_session_token", None)
            return None
        user, _session = resolved
        public = auth_service._to_public(user)
        st.session_state["_mpt_auth_user"] = public
        st.session_state["_mpt_session_token"] = token
        return public


def require_webui_auth() -> dict | None:
    """
    Gate the main WebUI. Returns user dict when authenticated.
    Returns None when auth disabled (caller continues normally).
    Stops the script when auth enabled and user must login/setup.
    """
    if not is_auth_enabled():
        return None

    try:
        run_auth_migrations()
        with session_scope() as db:
            needs_setup = auth_service.setup_required(db)
    except Exception:
        st.error("Authentication service temporarily unavailable.")
        st.stop()

    user = get_authenticated_user()

    # Multipage Setup/Login scripts handle their own UI; Main.py stops if unauthenticated.
    if user:
        return user

    if needs_setup:
        st.warning("Initial administrator setup is required.")
        st.info("Open the **Setup** page in the sidebar to create the first admin.")
        st.page_link("pages/0_Setup.py", label="Go to Setup", icon="🛡️")
        st.stop()

    st.info("Please log in to continue.")
    st.page_link("pages/Login.py", label="Go to Login", icon="🔑")
    st.stop()
    return None


def require_admin_user() -> dict:
    user = get_authenticated_user()
    if not user:
        st.switch_page("pages/Login.py")
        st.stop()
    if user.get("role") != UserRole.admin.value:
        st.error("You don't have permission to perform this action.")
        st.stop()
    return user


def render_logout_button() -> None:
    if not is_auth_enabled():
        return
    user = st.session_state.get("_mpt_auth_user")
    if not user:
        return
    cols = st.columns([4, 1])
    with cols[0]:
        st.caption(f"Signed in as **{user.get('username')}** ({user.get('role')})")
    with cols[1]:
        if st.button("Logout", use_container_width=True):
            token = st.session_state.get("_mpt_session_token")
            try:
                with session_scope() as db:
                    auth_service.logout(db, token)
            except Exception:
                pass
            st.session_state.pop("_mpt_session_token", None)
            st.session_state.pop("_mpt_auth_user", None)
            st.switch_page("pages/Login.py")

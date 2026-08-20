"""Initial administrator setup (only when users table is empty)."""

from __future__ import annotations

import os
import sys

import streamlit as st

root_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from app.auth import service as auth_service
from app.auth.db import session_scope
from app.auth.errors import AuthError
from app.auth.migrate import run_auth_migrations
from app.auth.settings import is_auth_enabled
from webui.auth_gate import establish_redirect_url, get_authenticated_user

st.set_page_config(page_title="Setup — MoneyPrinterTurbo", page_icon="🛡️", layout="centered")

st.title("Create Administrator")
st.caption("MoneyPrinterTurbo initial setup")

if not is_auth_enabled():
    st.warning("WARNING: Authentication is disabled.")
    st.stop()

try:
    run_auth_migrations()
    with session_scope() as db:
        needs_setup = auth_service.setup_required(db)
except Exception:
    st.error("Authentication service temporarily unavailable.")
    st.stop()

if not needs_setup:
    st.error("Initial setup is disabled.")
    if get_authenticated_user():
        st.page_link("Main.py", label="Open MoneyPrinterTurbo")
    else:
        st.page_link("pages/Login.py", label="Go to Login")
    st.stop()

with st.form("setup_form"):
    username = st.text_input("Username")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")
    submitted = st.form_submit_button("Create Administrator", type="primary")

if submitted:
    try:
        with session_scope() as db:
            user, raw_token, establish_code = auth_service.create_initial_admin(
                db,
                username=username,
                email=email,
                password=password,
                confirm_password=confirm,
            )
        st.session_state["_mpt_session_token"] = raw_token
        st.session_state["_mpt_auth_user"] = user
        st.success("Administrator created. Redirecting…")
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={establish_redirect_url(establish_code)}">',
            unsafe_allow_html=True,
        )
        st.link_button("Continue", establish_redirect_url(establish_code))
    except AuthError as exc:
        st.error(exc.message)

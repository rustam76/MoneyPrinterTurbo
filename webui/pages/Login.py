"""Login page for MoneyPrinterTurbo WebUI."""

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

st.set_page_config(page_title="Login — MoneyPrinterTurbo", page_icon="🔑", layout="centered")

st.title("MoneyPrinterTurbo")
st.caption("Sign in to continue")

if not is_auth_enabled():
    st.warning("WARNING: Authentication is disabled.")
    st.page_link("Main.py", label="Open MoneyPrinterTurbo")
    st.stop()

try:
    run_auth_migrations()
    with session_scope() as db:
        needs_setup = auth_service.setup_required(db)
except Exception:
    st.error("Authentication service temporarily unavailable.")
    st.stop()

if needs_setup:
    st.info("No administrator yet. Complete initial setup first.")
    st.page_link("pages/0_Setup.py", label="Go to Setup")
    st.stop()

existing = get_authenticated_user()
if existing:
    st.success(f"Already signed in as {existing['username']}")
    st.page_link("Main.py", label="Open MoneyPrinterTurbo")
    st.stop()

show_password = st.checkbox("Show password")
with st.form("login_form"):
    identifier = st.text_input("Username or Email")
    password = st.text_input(
        "Password", type="default" if show_password else "password"
    )
    submitted = st.form_submit_button("Login", type="primary")

if submitted:
    try:
        with session_scope() as db:
            user, raw_token, establish_code = auth_service.authenticate(
                db,
                username_or_email=identifier,
                password=password,
                client_ip="streamlit",
            )
        st.session_state["_mpt_session_token"] = raw_token
        st.session_state["_mpt_auth_user"] = user
        st.success("Login success.")
        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={establish_redirect_url(establish_code)}">',
            unsafe_allow_html=True,
        )
        st.link_button("Continue", establish_redirect_url(establish_code))
    except AuthError as exc:
        st.error(exc.message)

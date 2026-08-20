"""Admin user management (Streamlit)."""

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
from app.auth.settings import is_auth_enabled
from webui.auth_gate import render_logout_button, require_admin_user

st.set_page_config(page_title="Users — MoneyPrinterTurbo", page_icon="👥", layout="wide")

st.title("User Management")

if not is_auth_enabled():
    st.warning("WARNING: Authentication is disabled.")
    st.stop()

actor = require_admin_user()
render_logout_button()

st.subheader("Create user")
with st.form("create_user"):
    c_username = st.text_input("Username")
    c_email = st.text_input("Email")
    c_password = st.text_input("Password", type="password")
    c_role = st.selectbox("Role", ["user", "admin"])
    c_active = st.checkbox("Active", value=True)
    create_submitted = st.form_submit_button("Create User")

if create_submitted:
    try:
        with session_scope() as db:
            auth_service.create_user(
                db,
                username=c_username,
                email=c_email,
                password=c_password,
                role=c_role,
                is_active=c_active,
            )
        st.success("User created.")
        st.rerun()
    except AuthError as exc:
        st.error(exc.message)

st.subheader("Users")
with session_scope() as db:
    users = auth_service.list_users(db)

for user in users:
    with st.expander(f"{user['username']} ({user['role']})"):
        st.write(
            {
                "id": user["id"],
                "email": user["email"],
                "role": user["role"],
                "is_active": user["is_active"],
                "last_login_at": str(user.get("last_login_at")),
                "created_at": str(user.get("created_at")),
            }
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            new_role = st.selectbox(
                "Role",
                ["user", "admin"],
                index=0 if user["role"] == "user" else 1,
                key=f"role_{user['id']}",
            )
            if st.button("Save role", key=f"save_role_{user['id']}"):
                try:
                    with session_scope() as db:
                        auth_service.update_user(
                            db,
                            user_id=user["id"],
                            actor_id=actor["id"],
                            role=new_role,
                        )
                    st.rerun()
                except AuthError as exc:
                    st.error(exc.message)
        with col2:
            new_password = st.text_input(
                "Reset password", type="password", key=f"pw_{user['id']}"
            )
            if st.button("Reset Password", key=f"reset_{user['id']}"):
                try:
                    with session_scope() as db:
                        auth_service.reset_password(
                            db, user_id=user["id"], password=new_password
                        )
                    st.success("Password updated.")
                except AuthError as exc:
                    st.error(exc.message)
        with col3:
            if user["is_active"]:
                if st.button("Deactivate", key=f"deact_{user['id']}"):
                    try:
                        with session_scope() as db:
                            auth_service.set_user_active(
                                db,
                                user_id=user["id"],
                                actor_id=actor["id"],
                                is_active=False,
                            )
                        st.rerun()
                    except AuthError as exc:
                        st.error(exc.message)
            else:
                if st.button("Activate", key=f"act_{user['id']}"):
                    try:
                        with session_scope() as db:
                            auth_service.set_user_active(
                                db,
                                user_id=user["id"],
                                actor_id=actor["id"],
                                is_active=True,
                            )
                        st.rerun()
                    except AuthError as exc:
                        st.error(exc.message)
        with col4:
            if st.button("Delete", key=f"del_{user['id']}"):
                try:
                    with session_scope() as db:
                        auth_service.delete_user(
                            db, user_id=user["id"], actor_id=actor["id"]
                        )
                    st.rerun()
                except AuthError as exc:
                    st.error(exc.message)

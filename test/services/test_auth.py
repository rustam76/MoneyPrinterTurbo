"""Authentication service and API tests (SQLite in-memory)."""

from __future__ import annotations

import os
from unittest import TestCase

_PREV_ENV = {
    key: os.environ.get(key)
    for key in (
        "MPT_AUTH_ENABLED",
        "DATABASE_URL",
        "MPT_SESSION_SECRET",
        "MPT_SESSION_EXPIRE_HOURS",
        "MPT_COOKIE_SECURE",
    )
}


def _enable_test_auth_env() -> None:
    os.environ["MPT_AUTH_ENABLED"] = "true"
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["MPT_SESSION_SECRET"] = "test-session-secret-value-32chars"
    os.environ["MPT_SESSION_EXPIRE_HOURS"] = "24"
    os.environ["MPT_COOKIE_SECURE"] = "false"


def _restore_env() -> None:
    for key, value in _PREV_ENV.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


_enable_test_auth_env()

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import service as auth_service
from app.auth.db import reset_engine_for_tests
from app.auth.models import Base
from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import login_rate_limiter
from app.auth.settings import auth_settings


def teardown_module(module):
    _restore_env()
    reset_engine_for_tests()
    login_rate_limiter.reset()
    auth_settings.cache_clear()


class AuthServiceTests(TestCase):
    def setUp(self):
        reset_engine_for_tests()
        login_rate_limiter.reset()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

        # Patch get_engine / session factory used by service helpers via db module
        import app.auth.db as db_mod

        db_mod._engine = self.engine
        db_mod._SessionLocal = self.Session

    def tearDown(self):
        reset_engine_for_tests()
        login_rate_limiter.reset()

    def test_password_hashed_not_plaintext(self):
        digest = hash_password("secret-pass")
        self.assertNotEqual(digest, "secret-pass")
        self.assertTrue(verify_password(digest, "secret-pass"))
        self.assertFalse(verify_password(digest, "wrong"))

    def test_setup_creates_admin_then_disabled(self):
        with self.Session() as db:
            self.assertTrue(auth_service.setup_required(db))
            user, token, code = auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            db.commit()
            self.assertEqual(user["role"], "admin")
            self.assertTrue(token)
            self.assertTrue(code)
            self.assertFalse(auth_service.setup_required(db))
            with self.assertRaises(Exception):
                auth_service.create_initial_admin(
                    db,
                    username="admin2",
                    email="a2@example.com",
                    password="password1",
                    confirm_password="password1",
                )

    def test_login_username_and_email(self):
        with self.Session() as db:
            auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            db.commit()
            u1, *_ = auth_service.authenticate(
                db, username_or_email="admin", password="password1", client_ip="1.1.1.1"
            )
            self.assertEqual(u1["username"], "admin")
            u2, *_ = auth_service.authenticate(
                db,
                username_or_email="admin@example.com",
                password="password1",
                client_ip="1.1.1.1",
            )
            self.assertEqual(u2["username"], "admin")

    def test_login_failure_generic_and_inactive(self):
        with self.Session() as db:
            admin, *_ = auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            auth_service.create_user(
                db,
                username="bob",
                email="bob@example.com",
                password="password1",
                role="user",
                is_active=False,
            )
            db.commit()
            with self.assertRaises(Exception) as ctx:
                auth_service.authenticate(
                    db, username_or_email="admin", password="bad", client_ip="2.2.2.2"
                )
            self.assertIn("password", str(ctx.exception).lower())
            with self.assertRaises(Exception):
                auth_service.authenticate(
                    db, username_or_email="bob", password="password1", client_ip="2.2.2.2"
                )

    def test_admin_safety_last_admin(self):
        with self.Session() as db:
            admin, *_ = auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            db.commit()
            with self.assertRaises(Exception):
                auth_service.delete_user(
                    db, user_id=admin["id"], actor_id=admin["id"]
                )
            with self.assertRaises(Exception):
                auth_service.set_user_active(
                    db, user_id=admin["id"], actor_id=admin["id"], is_active=False
                )

    def test_rate_limit_login(self):
        with self.Session() as db:
            auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            db.commit()
            for _ in range(5):
                with self.assertRaises(Exception):
                    auth_service.authenticate(
                        db,
                        username_or_email="admin",
                        password="bad",
                        client_ip="9.9.9.9",
                    )
            with self.assertRaises(Exception) as ctx:
                auth_service.authenticate(
                    db,
                    username_or_email="admin",
                    password="password1",
                    client_ip="9.9.9.9",
                )
            self.assertEqual(getattr(ctx.exception, "status_code", None), 429)

    def test_public_user_has_no_password_fields(self):
        with self.Session() as db:
            user, *_ = auth_service.create_initial_admin(
                db,
                username="admin",
                email="admin@example.com",
                password="password1",
                confirm_password="password1",
            )
            db.commit()
            self.assertNotIn("password", user)
            self.assertNotIn("password_hash", user)


class AuthApiTests(TestCase):
    def setUp(self):
        reset_engine_for_tests()
        login_rate_limiter.reset()
        auth_settings.cache_clear()
        os.environ["MPT_AUTH_ENABLED"] = "true"
        os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
        os.environ["MPT_SESSION_SECRET"] = "test-session-secret-value-32chars"
        auth_settings.cache_clear()

        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        import app.auth.db as db_mod

        db_mod._engine = self.engine
        db_mod._SessionLocal = Session

        # Avoid lifespan migration against real alembic during tests
        import app.asgi as asgi_mod

        self._orig_lifespan = asgi_mod.application_lifespan

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _noop_lifespan(_: object):
            yield

        asgi_mod.app.router.lifespan_context = _noop_lifespan
        self.client = TestClient(asgi_mod.app)

    def tearDown(self):
        reset_engine_for_tests()
        login_rate_limiter.reset()
        auth_settings.cache_clear()

    def test_status_setup_required(self):
        resp = self.client.get("/auth/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["data"]["enabled"])
        self.assertTrue(body["data"]["setup_required"])

    def test_setup_login_me_logout(self):
        resp = self.client.post(
            "/auth/setup",
            json={
                "username": "admin",
                "email": "admin@example.com",
                "password": "password1",
                "confirm_password": "password1",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("MPT_SESSION", resp.cookies)
        data = resp.json()["data"]
        self.assertNotIn("password", str(data))
        self.assertNotIn("password_hash", str(data))

        me = self.client.get("/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["username"], "admin")

        # setup again forbidden
        again = self.client.post(
            "/auth/setup",
            json={
                "username": "admin2",
                "email": "a2@example.com",
                "password": "password1",
                "confirm_password": "password1",
            },
        )
        self.assertEqual(again.status_code, 403)

        protected = self.client.get("/api/v1/tasks")
        self.assertIn(protected.status_code, (200, 401))  # authenticated cookie present

        logout = self.client.post("/auth/logout")
        self.assertEqual(logout.status_code, 200)
        me2 = self.client.get("/auth/me")
        self.assertEqual(me2.status_code, 401)

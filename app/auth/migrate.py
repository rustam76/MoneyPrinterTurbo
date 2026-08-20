"""Create database tables / run migrations when auth is enabled."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from alembic import command
from alembic.config import Config

from app.auth.db import check_database, get_engine
from app.auth.models import Base
from app.auth.settings import is_auth_enabled, mask_database_url, require_auth_config


def run_auth_migrations() -> None:
    if not is_auth_enabled():
        return
    settings = require_auth_config()
    try:
        check_database()
    except Exception as exc:
        logger.error(
            "Authentication database is unavailable ({})",
            mask_database_url(settings.database_url),
        )
        raise RuntimeError("Authentication database is unavailable.") from exc

    root = Path(__file__).resolve().parents[2]
    alembic_ini = root / "alembic.ini"
    if alembic_ini.exists():
        cfg = Config(str(alembic_ini))
        cfg.set_main_option("sqlalchemy.url", settings.database_url)
        command.upgrade(cfg, "head")
        logger.info("Authentication migrations applied.")
        return

    # Fallback: create tables from models (tests / missing alembic.ini)
    Base.metadata.create_all(bind=get_engine())
    logger.info("Authentication tables ensured via metadata.create_all.")

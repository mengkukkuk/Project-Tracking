"""Application configuration.

Settings are read from environment variables (a local ``.env`` file is loaded
automatically when present). Sensible, zero-config defaults are provided so the
app boots out of the box for local development and demos.
"""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


class Config:
    # --- Core -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-0123456789abcdef")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_HOURS", "12"))
    )

    # --- Database -------------------------------------------------------
    # PostgreSQL: postgresql+psycopg2://user:pass@host:5432/ProjectTracking
    # MSSQL:      mssql+pyodbc://user:pass@host/ProjectTracking?driver=ODBC+Driver+18+for+SQL+Server
    # SQLite (default): zero-config fallback for local dev / demo
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///project_tracking.db")

    # --- CORS -----------------------------------------------------------
    # Comma-separated list of allowed origins. "*" allows any (dev only).
    # Empty string = same-origin only (safe default for production).
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")

    # --- Misc -----------------------------------------------------------
    DEBUG = _bool("FLASK_DEBUG", False)
    SEED_ON_START = _bool("SEED_ON_START", False)


class TestConfig(Config):
    TESTING = True
    DATABASE_URL = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-secret"
    SECRET_KEY = "test-secret"

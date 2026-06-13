"""Application configuration.

Settings are read from environment variables (a local ``.env`` file is loaded
automatically when present). Sensible, zero-config defaults are provided so the
app boots out of the box for local development and demos.
"""
import os
from datetime import timedelta
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


def _database_url() -> str:
    """Resolve the SQLAlchemy URL.

    Precedence: an explicit ``DATABASE_URL`` wins; otherwise a PostgreSQL URL is
    assembled from the discrete ``DB_*`` parts (password is percent-encoded so
    special characters like ``@`` are safe); otherwise a zero-config SQLite
    fallback keeps the app booting out of the box.
    """
    explicit = os.getenv("DATABASE_URL")
    if explicit:
        return explicit

    host = os.getenv("DB_HOST")
    if host:
        user = os.getenv("DB_USER", "postgres")
        password = quote_plus(os.getenv("DB_PASSWORD", ""))
        port = os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "postgres")
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

    return "sqlite:///project_tracking.db"


class Config:
    # --- Core -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me-0123456789abcdef")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_HOURS", "12"))
    )

    # --- Database -------------------------------------------------------
    # Set DATABASE_URL directly, or supply discrete DB_HOST/DB_PORT/DB_NAME/
    # DB_USER/DB_PASSWORD parts (assembled into a PostgreSQL URL). Falls back
    # to zero-config SQLite for local dev / demo.
    #   PostgreSQL: postgresql+psycopg2://user:pass@host:5432/ProjectTracking
    #   MSSQL:      mssql+pyodbc://user:pass@host/ProjectTracking?driver=ODBC+Driver+18+for+SQL+Server
    DATABASE_URL = _database_url()

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

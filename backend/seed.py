"""Convenience wrapper so ``python seed.py`` works from the backend root.

Creates the app context (which builds the schema) and loads demo data.

On PostgreSQL the SQLAlchemy engine is configured with ``search_path=pjtrk``
(see ``app/extensions.py``), so the ``pjtrk`` schema must exist *before*
``create_app()`` runs ``Base.metadata.create_all()``. We bootstrap it here so
this script is self-sufficient on a fresh database — no need to run
``init_db.sql`` first.
"""
from sqlalchemy import create_engine, text

from app import create_app
from app.config import Config
from app.seed import seed


def _bootstrap_pg_schema(url: str) -> None:
    if not url.startswith("postgresql"):
        return
    eng = create_engine(url, future=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS pjtrk"))
            conn.commit()
    finally:
        eng.dispose()


if __name__ == "__main__":
    _bootstrap_pg_schema(Config.DATABASE_URL)
    app = create_app()
    with app.app_context():
        seed()

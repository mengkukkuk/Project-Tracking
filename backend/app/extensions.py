"""Shared extension singletons and the SQLAlchemy session lifecycle.

A single ``scoped_session`` is bound to the engine when the app is created. The
session is removed at the end of every request via a teardown hook (registered
in ``app/__init__.py``) so connections are never leaked between requests.
"""
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker

jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Populated by init_engine() at app-creation time.
engine = None
Session = scoped_session(sessionmaker(future=True))


def init_engine(database_url: str):
    """(Re)bind the global engine and session factory to "database_url"."""
    global engine
    connect_args = {}
    if database_url.startswith("sqlite"):
        # Allow the in-memory/file DB to be shared across threads (Flask dev server).
        connect_args["check_same_thread"] = False
    elif database_url.startswith("postgresql"):
        connect_args["options"] = "-csearch_path=pjtrk"

    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    # SQLite ignores ``ON DELETE CASCADE`` unless foreign-key enforcement is
    # turned on per-connection. PostgreSQL enforces FKs natively, so this
    # keeps dev/test behavior consistent with production.
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_fk_pragma(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    Session.configure(bind=engine)
    return engine

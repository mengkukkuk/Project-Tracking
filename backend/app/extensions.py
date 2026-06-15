"""Shared extension singletons and the SQLAlchemy session lifecycle.

A single ``scoped_session`` is bound to the engine when the app is created. The
session is removed at the end of every request via a teardown hook (registered
in ``app/__init__.py``) so connections are never leaked between requests.
"""
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Populated by init_engine() at app-creation time.
engine = None
Session = scoped_session(sessionmaker(future=True))


def init_engine(database_url: str):
    """(Re)bind the global engine and session factory to ``database_url``."""
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
    Session.configure(bind=engine)
    return engine

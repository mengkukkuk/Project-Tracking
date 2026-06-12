"""Application factory.

    from app import create_app
    app = create_app()

Wires up config, the database engine, JWT, CORS, error handlers and all
blueprints. Tables are created on startup (and demo data seeded when
``SEED_ON_START`` is enabled).
"""
from flask import Flask
from flask_cors import CORS

from .api import blueprints as api_blueprints
from .auth import bp as auth_bp
from .config import Config
from .errors import register_error_handlers
from .extensions import Session, engine, init_engine, jwt, limiter
from .models import Base


def create_app(config: Config = None) -> Flask:
    config = config or Config
    app = Flask(__name__)
    app.config.from_object(config)

    # Database
    eng = init_engine(config.DATABASE_URL)

    # Extensions
    jwt.init_app(app)
    limiter.init_app(app)
    origins = config.CORS_ORIGINS
    if origins == "*":
        allowed_origins = "*"
    elif origins:
        allowed_origins = [o.strip() for o in origins.split(",") if o.strip()]
    else:
        allowed_origins = []
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # JWT error responses share the standard envelope.
    @jwt.unauthorized_loader
    def _missing_token(reason):
        return {"error": {"type": "auth", "message": reason}}, 401

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return {"error": {"type": "auth", "message": reason}}, 401

    @jwt.expired_token_loader
    def _expired_token(header, payload):
        return {"error": {"type": "auth", "message": "Token has expired"}}, 401

    # Blueprints
    app.register_blueprint(auth_bp)
    for bp in api_blueprints:
        app.register_blueprint(bp)

    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        return {"ok": True, "db": eng.url.get_backend_name()}

    # Release the scoped session at the end of every request.
    @app.teardown_appcontext
    def _remove_session(exc=None):
        Session.remove()

    # Schema bootstrap
    Base.metadata.create_all(eng)
    if app.config.get("SEED_ON_START"):
        from .seed import seed

        seed()

    return app

"""Authentication blueprint: register, login, and current-user lookup.

Uses JWT access tokens (Flask-JWT-Extended). Passwords are hashed with
Werkzeug's PBKDF2. The JWT identity is the stringified user id; the user's role
is carried as an additional claim for cheap authorization checks.
"""
from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from .extensions import Session, limiter
from .models import User
from .validation import require_dict, str_field

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def current_user():
    """Return the authenticated User, or None. Requires an active JWT context."""
    uid = get_jwt_identity()
    if uid is None:
        return None
    return Session.get(User, int(uid))


def _token_for(user: User) -> str:
    return create_access_token(
        identity=str(user.id), additional_claims={"role": user.role, "name": user.name}
    )


@bp.post("/register")
@limiter.limit("5 per minute")
def register():
    """POST /api/auth/register — create a new user and return a JWT.

    Body: {name, email, password (>=8 chars)}. Rate-limited 5/min/IP. The very
    first registered user is promoted to ``admin``; everyone else is a member.
    """
    data = require_dict(request.get_json(silent=True))
    name = str_field(data, "name", required=True, max_len=128)
    email = str_field(data, "email", required=True, max_len=255).lower()
    password = str_field(data, "password", required=True)
    if len(password) < 8:
        from .validation import ValidationError

        raise ValidationError({"password": "must be at least 8 characters"})

    if Session.query(User).filter_by(email=email).first():
        from .validation import ValidationError

        raise ValidationError({"email": "is already registered"})

    # First user to register becomes admin; everyone else is a member.
    role = "admin" if Session.query(User).count() == 0 else "member"
    user = User(name=name, email=email, role=role)
    user.set_password(password)
    Session.add(user)
    Session.commit()
    return {"token": _token_for(user), "user": user.to_dict()}, 201


@bp.post("/login")
@limiter.limit("10 per minute")
def login():
    """POST /api/auth/login — exchange email/password for a JWT.

    Body: {email, password}. Rate-limited 10/min/IP. Returns 401 on bad creds.
    """
    data = require_dict(request.get_json(silent=True))
    email = str_field(data, "email", required=True).lower()
    password = str_field(data, "password", required=True)

    user = Session.query(User).filter_by(email=email).first()
    if not user or not user.check_password(password):
        return {"error": {"type": "auth", "message": "Invalid email or password"}}, 401
    return {"token": _token_for(user), "user": user.to_dict()}


@bp.get("/me")
@jwt_required()
def me():
    """GET /api/auth/me — return the authenticated user + role claim.

    Used by the SPA to restore session state on page reload.
    """
    user = current_user()
    if not user:
        return {"error": {"type": "auth", "message": "User not found"}}, 401
    return {"user": user.to_dict(), "role": get_jwt().get("role")}

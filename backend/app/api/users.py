"""Users resource (read-only): powers owner/assignee pickers in the UI."""
from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import Session
from ..models import User

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@jwt_required()
def list_users():
    rows = Session.query(User).order_by(User.name.asc()).all()
    return {"items": [u.to_dict() for u in rows]}

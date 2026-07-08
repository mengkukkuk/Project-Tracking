"""Users resource: read-only directory + super-admin role assignment."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import ROLES, User
from ..validation import ValidationError, require_dict, str_field
from .helpers import require_permission

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("")
@jwt_required()
def list_users():
    """GET /api/users — list all users (name, email, role, permissions).

    Read-only directory used by the SPA's owner/assignee picker dropdowns and
    the role-management screen.
    """
    rows = Session.query(User).order_by(User.name.asc()).all()
    return {"items": [u.to_dict() for u in rows]}


@bp.patch("/<int:uid>/role")
@jwt_required()
def set_user_role(uid):
    """PATCH /api/users/<uid>/role — assign a role to a user.

    Body: {role}. Requires the ``roles.assign`` capability (admin / super_admin).
    Guardrails, enforced server-side regardless of what the UI shows:
      * Only a super_admin may grant the super_admin role, or modify a user who
        is currently super_admin (an admin cannot create or demote a peer above
        itself).
      * You cannot change your own role (prevents accidental self-lockout).
    """
    actor = current_user()
    denied = require_permission(actor, "roles.assign")
    if denied:
        return denied

    data = require_dict(request.get_json(silent=True))
    new_role = str_field(data, "role", required=True)
    if new_role not in ROLES:
        raise ValidationError({"role": f"must be one of {', '.join(ROLES)}"})

    target = Session.get(User, uid)
    if not target:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404

    if target.id == actor.id:
        return {
            "error": {"type": "http", "code": 403, "message": "Cannot change your own role"}
        }, 403

    # Only a super_admin may grant or touch the super_admin role.
    touches_super = new_role == "super_admin" or target.role == "super_admin"
    if touches_super and actor.role != "super_admin":
        return {
            "error": {
                "type": "http",
                "code": 403,
                "message": "Only a super admin may assign or modify the super admin role",
            }
        }, 403

    target.role = new_role
    Session.commit()
    return target.to_dict()
"""Users resource: read-only directory + super-admin role assignment."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import ELEVATED_ROLES, ROLES, User
from ..permissions import PAGE_KEYS
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
    # Promotion to an elevated role invalidates any page restriction (elevated
    # roles always see every page); clear it so a later demotion lands on the
    # default (all pages) rather than silently re-applying a stale override.
    if new_role in ELEVATED_ROLES:
        target.page_access = None
    Session.commit()
    return target.to_dict()


@bp.patch("/<int:uid>/pages")
@jwt_required()
def set_user_pages(uid):
    """PATCH /api/users/<uid>/pages — set which side-nav pages a member may open.

    Body: {pages: [<page key>, ...]}. Requires the ``pages.assign`` capability
    (admin / super_admin). Members only: elevated targets are rejected — they
    always hold every page. At least one page is required — a member must have
    somewhere to land. Saving the full catalog clears the override (page_access
    -> NULL = default all, so future new pages are automatically included).
    No self-change guard is needed: any actor holding pages.assign is elevated,
    and elevated targets are already rejected by the guard below.
    """
    actor = current_user()
    denied = require_permission(actor, "pages.assign")
    if denied:
        return denied

    data = require_dict(request.get_json(silent=True))
    pages = data.get("pages")
    if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
        raise ValidationError({"pages": "must be a list of page keys"})
    keys = {p.strip() for p in pages}
    invalid = keys - set(PAGE_KEYS)
    if invalid:
        raise ValidationError({"pages": f"unknown page keys: {', '.join(sorted(invalid))}"})
    if not keys:
        raise ValidationError({"pages": "at least one page is required"})

    target = Session.get(User, uid)
    if not target:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404

    if target.role in ELEVATED_ROLES:
        return {
            "error": {
                "type": "http",
                "code": 403,
                "message": "Page access can only be set for members",
            }
        }, 403

    target.page_access = None if keys == set(PAGE_KEYS) else ",".join(
        k for k in PAGE_KEYS if k in keys
    )
    Session.commit()
    return target.to_dict()
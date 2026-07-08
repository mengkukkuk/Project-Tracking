"""Comments on a project."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import ELEVATED_ROLES, Comment, Project
from ..validation import require_dict, str_field

bp = Blueprint("comments", __name__, url_prefix="/api")


@bp.post("/projects/<int:pid>/comments")
@jwt_required()
def create_comment(pid):
    """POST /api/projects/<pid>/comments — add a comment to a project.

    Body: {body (required)}. Author is taken from the JWT. 404 if no project.
    """
    p = Session.get(Project, pid)
    if not p:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    data = require_dict(request.get_json(silent=True))
    user = current_user()
    comment = Comment(
        project_id=pid,
        user_id=user.id if user else None,
        body=str_field(data, "body", required=True),
    )
    Session.add(comment)
    Session.commit()
    return comment.to_dict(), 201


@bp.delete("/comments/<int:cid>")
@jwt_required()
def delete_comment(cid):
    """DELETE /api/comments/<cid> — author or admin only.

    Note: deviates from the standard owner/admin helper because the relevant
    "owner" here is the comment's author, not the parent project's owner.
    """
    comment = Session.get(Comment, cid)
    if not comment:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    # Only the author or an elevated role (admin / super_admin) may delete.
    # Ownership here is the comment's author, not the parent project's owner,
    # so this stays a bespoke check rather than require_owner_or_admin.
    if user and user.role not in ELEVATED_ROLES and comment.user_id != user.id:
        return {"error": {"type": "http", "code": 403, "message": "Forbidden"}}, 403
    Session.delete(comment)
    Session.commit()
    return "", 204

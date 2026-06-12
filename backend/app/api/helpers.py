"""Shared helpers for API resources: activity logging and authorization."""
from ..extensions import Session
from ..models import Activity


def log_activity(project_id, action, detail, user):
    """Append an entry to a project's activity feed (does not commit)."""
    Session.add(
        Activity(
            project_id=project_id,
            user_id=user.id if user else None,
            action=action,
            detail=detail,
        )
    )


def require_owner_or_admin(user, owner_id):
    """Return a 403 response tuple if user is not the owner or an admin, else None."""
    if user is None or (user.role != "admin" and user.id != owner_id):
        return {"error": {"type": "http", "code": 403, "message": "Forbidden"}}, 403
    return None

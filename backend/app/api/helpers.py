"""Shared helpers for API resources: activity logging."""
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

"""Shared helpers for API resources: activity logging and authorization."""
from datetime import timedelta

from ..extensions import Session
from ..models import Activity, ProcessTag, Project, PTrack


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


def recompute_ptrack_dates(project_id):
    """Persist canonical start_date / due_date on every ptrack row of a project.

    Chain (matches the UI):
        first process:  start = project.start_date,    due = start + day_range
        subsequent:     start = previous due + 1 day,  due = start + day_range

    Canonical order is process_tags.processid asc. No-ops silently if the
    project has no start_date or no process tags configured.

    Caller does NOT need to commit — this function commits its own changes
    when any row was modified.
    """
    project = Session.get(Project, project_id)
    if not project or not project.start_date:
        return 0

    tag_chain = (
        Session.query(ProcessTag.process, ProcessTag.day_range)
        .order_by(ProcessTag.processid.asc())
        .all()
    )
    group_dates = {}
    prev_due = None
    for name, dr in tag_chain:
        if dr is None or name is None:
            continue
        start = (prev_due + timedelta(days=1)) if prev_due else project.start_date
        due = start + timedelta(days=int(dr))
        group_dates[name] = (start, due)
        prev_due = due

    if not group_dates:
        return 0

    rows = Session.query(PTrack).filter(PTrack.project_id == project_id).all()
    changed = 0
    for r in rows:
        dates = group_dates.get(r.process)
        if not dates:
            continue
        start, due = dates
        if r.start_date != start or r.due_date != due:
            r.start_date = start
            r.due_date = due
            changed += 1
    if changed:
        Session.commit()
    return changed

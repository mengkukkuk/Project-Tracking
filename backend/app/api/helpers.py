"""Shared helpers for API resources: activity logging and authorization."""
from datetime import date, timedelta

from ..extensions import Session
from ..models import Activity, ProcessTag, Project, PTrack, Task, derived_status


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


def recompute_project_status(project_id):
    """Persist Project.status derived from the live progress %.

    Status is no longer a free-form column the user can set — it's a 5-bucket
    projection of the process-checklist progress (with task counts as a
    fallback). Keeping it persisted means the list view, stats SQL GROUP BY,
    and kanban groupings stay correct without recomputing per-row.

    Commits only when the status changes. No-op if the project is missing.
    """
    project = Session.get(Project, project_id)
    if not project:
        return False
    ptracks = Session.query(PTrack).filter(PTrack.project_id == project_id).all()
    ptotal = len(ptracks)
    pdone = sum(1 for r in ptracks if r.checked)
    if ptotal:
        live = round((pdone / ptotal) * 100)
    else:
        tasks = Session.query(Task).filter(Task.project_id == project_id).all()
        if tasks:
            live = round((sum(1 for t in tasks if t.done) / len(tasks)) * 100)
        else:
            live = int(project.progress or 0)
    new_status = derived_status(live)
    if project.status != new_status:
        project.status = new_status
        Session.commit()
        return True
    return False


# Stable status labels — frontend pairs these with colors (green/orange/red).
PTRACK_STATUS_DONE = "Done"
PTRACK_STATUS_IN_PROGRESS = "In progress"
PTRACK_STATUS_NOT_STARTED = "Not started"


def recompute_ptrack_status(project_id):
    """Persist a per-task status on every ptrack row of a project.

    Status is derived per row from the checkbox state and the row's start_date:
        checked                                  -> "Done"
        not checked and today >= row.start_date  -> "In progress"
        otherwise (future / no start_date)       -> "Not started"

    Commits only when at least one row changed. Returns the number of rows
    updated. Callers should run :func:`recompute_ptrack_dates` first so each
    row has a current start_date to compare against.
    """
    rows = Session.query(PTrack).filter(PTrack.project_id == project_id).all()
    if not rows:
        return 0

    today = date.today()
    changed = 0
    for r in rows:
        if r.checked:
            new_status = PTRACK_STATUS_DONE
        elif r.start_date is not None and today >= r.start_date:
            new_status = PTRACK_STATUS_IN_PROGRESS
        else:
            new_status = PTRACK_STATUS_NOT_STARTED
        if r.status != new_status:
            r.status = new_status
            changed += 1
    if changed:
        Session.commit()
    return changed

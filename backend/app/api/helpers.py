"""Shared helpers for API resources: activity logging and authorization."""
from datetime import date, timedelta

from sqlalchemy import func

from ..extensions import Session
from ..models import (
    ELEVATED_ROLES,
    Activity,
    ProcessTag,
    Project,
    PTemplate,
    PTrack,
    Task,
    derived_status,
)

DEFAULT_TEMPLATE_NO = 1
# ``projects.template_no = 0``: the project was disconnected from its template
# (NULL can't be used — it already means template 1). It keeps its ptrack rows,
# and those rows act as its own template (see :func:`process_chain`).
DETACHED_TEMPLATE_NO = 0


def project_template_no(project):
    """Template a project was created from; legacy NULL means template 1."""
    no = project.template_no if project else None
    return DEFAULT_TEMPLATE_NO if no is None else no


def process_chain(project):
    """Canonical ``[(process, day_range)]`` order driving a project's date chain.

    Normally the project's template ``process_tags`` (by processid). A detached
    project has no template, so the chain is read back from its own ptrack rows:
    each process's day budget is its persisted ``due - start`` (exactly what
    :func:`recompute_ptrack_dates` wrote while it was attached), ordered by start
    date. Processes without dates get ``None`` and sort last.
    """
    no = project_template_no(project)
    if no != DETACHED_TEMPLATE_NO:
        return (
            Session.query(ProcessTag.process, ProcessTag.day_range)
            .filter(tag_in_template(no))
            .order_by(ProcessTag.processid.asc())
            .all()
        )
    spans = {}  # process -> [min start, max due, min id]
    rows = Session.query(PTrack).filter(PTrack.project_id == project.id).order_by(PTrack.id)
    for r in rows.all():
        if r.process is None:
            continue
        s = spans.setdefault(r.process, [None, None, r.id])
        if r.start_date and (s[0] is None or r.start_date < s[0]):
            s[0] = r.start_date
        if r.due_date and (s[1] is None or r.due_date > s[1]):
            s[1] = r.due_date
    ordered = sorted(spans.items(), key=lambda kv: (kv[1][0] or date.max, kv[1][2]))
    return [
        (name, (due - start).days if start and due else None)
        for name, (start, due, _) in ordered
    ]


def tag_in_template(template_no):
    """Filter clause: process_tags rows of ``template_no`` (NULL counts as 1)."""
    return func.coalesce(ProcessTag.template_no, DEFAULT_TEMPLATE_NO) == template_no


def ptemplate_in_template(template_no):
    """Filter clause: ptemplate rows of ``template_no`` (NULL counts as 1)."""
    return func.coalesce(PTemplate.template_no, DEFAULT_TEMPLATE_NO) == template_no


def template_exists(template_no):
    """A template exists iff it has at least one process_tags row."""
    return (
        Session.query(ProcessTag.id).filter(tag_in_template(template_no)).first()
        is not None
    )


def _forbidden():
    return {"error": {"type": "http", "code": 403, "message": "Forbidden"}}, 403


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
    """Return a 403 response tuple if user is neither the owner nor an elevated
    role (admin / super_admin), else None.

    This is the *scope* gate: elevated roles act on any row; everyone else only
    on rows they own. Capability is gated separately via require_permission.
    """
    if user is None or (user.role not in ELEVATED_ROLES and user.id != owner_id):
        return _forbidden()
    return None


def require_permission(user, perm):
    """Return a 403 response tuple if ``user`` lacks capability ``perm``, else
    None. Resolves against the live DB role (wildcard-aware), so role changes
    take effect immediately without waiting for a token to expire.
    """
    if user is None or not user.has_permission(perm):
        return _forbidden()
    return None


def recompute_ptrack_dates(project_id):
    """Persist canonical start_date / due_date on every ptrack row of a project.

    Chain (matches the UI):
        first process:  start = project.start_date,    due = start + day_range
        subsequent:     start = previous due + 1 day,  due = start + day_range

    Canonical order is process_tags.processid asc within the project's own
    template (``projects.template_no``). No-ops silently if the
    project has no start_date or no process tags configured.

    Caller does NOT need to commit — this function commits its own changes
    when any row was modified.
    """
    project = Session.get(Project, project_id)
    if not project or not project.start_date:
        return 0

    tag_chain = process_chain(project)
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

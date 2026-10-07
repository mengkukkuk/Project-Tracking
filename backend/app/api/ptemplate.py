"""Process template resources.

A *template* is the set of ``process_tags`` (processes + day budgets) and
``ptemplate`` (tasks) rows sharing a ``template_no``. A project picks one
template at creation; only that template seeds its ``ptrack`` checklist and
drives its due-date chain. ``processid`` is unique only *within* a template.

There is no ``templates`` table: a template exists iff it has at least one
``process_tags`` row, so a new template is born with a starter process and its
last process cannot be deleted. Reads are open to any authenticated user (the
New Project picker needs them); writes require ``templates.manage``. Editing a
template never touches existing projects' ``ptrack`` (snapshot semantics).
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ..auth import current_user
from ..extensions import Session
from ..models import ProcessTag, Project, PTemplate, TemplateName
from ..validation import ValidationError, int_field, require_dict, str_field
from .helpers import (
    DEFAULT_TEMPLATE_NO,
    ptemplate_in_template,
    require_permission,
    tag_in_template,
    template_exists,
)

bp = Blueprint("ptemplate", __name__, url_prefix="/api")

_NO = func.coalesce(ProcessTag.template_no, DEFAULT_TEMPLATE_NO)
_TASK_NO = func.coalesce(PTemplate.template_no, DEFAULT_TEMPLATE_NO)
_PROJECT_NO = func.coalesce(Project.template_no, DEFAULT_TEMPLATE_NO)


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _conflict(message):
    return {"error": {"type": "http", "code": 409, "message": message}}, 409


def _template_no_of(row):
    return row.template_no or DEFAULT_TEMPLATE_NO


# ── Templates (read) ──────────────────────────────────────────────────────────


@bp.get("/templates")
@jwt_required()
def list_templates():
    """GET /api/templates — every template with process/task/project counts."""
    proc = dict(
        Session.query(_NO, func.count(ProcessTag.id)).group_by(_NO).all()
    )
    tasks = dict(
        Session.query(_TASK_NO, func.count(PTemplate.id)).group_by(_TASK_NO).all()
    )
    used = dict(
        Session.query(_PROJECT_NO, func.count(Project.id)).group_by(_PROJECT_NO).all()
    )
    names = dict(Session.query(TemplateName.template_no, TemplateName.name).all())
    return {
        "items": [
            {
                "templateNo": no,
                "name": names.get(no),
                "processCount": proc[no],
                "taskCount": tasks.get(no, 0),
                "projectCount": used.get(no, 0),
            }
            for no in sorted(proc)
        ]
    }


@bp.get("/templates/<int:no>")
@jwt_required()
def get_template(no):
    """GET /api/templates/<no> — processes (by processid) each with its tasks."""
    tags = (
        Session.query(ProcessTag)
        .filter(tag_in_template(no))
        .order_by(ProcessTag.processid.asc(), ProcessTag.id.asc())
        .all()
    )
    if not tags:
        return _not_found()
    tasks = (
        Session.query(PTemplate)
        .filter(ptemplate_in_template(no))
        .order_by(PTemplate.id.asc())
        .all()
    )
    by_process = {}
    for t in tasks:
        by_process.setdefault(t.processid, []).append(t.to_dict())
    name = Session.get(TemplateName, no)
    return {
        "templateNo": no,
        "name": name.name if name else None,
        "processes": [
            {**tag.to_dict(), "tasks": by_process.get(tag.processid, [])}
            for tag in tags
        ],
    }


# ── Templates (write) ─────────────────────────────────────────────────────────


@bp.post("/templates")
@jwt_required()
def create_template():
    """POST /api/templates — new ``template_no`` (max + 1).

    Body: ``{cloneFrom?, name?}``. With ``cloneFrom`` the source template's processes
    and tasks are copied; otherwise the template starts with a single starter
    process so that it exists (see module docstring).
    """
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))
    clone_from = int_field(data, "cloneFrom", minimum=1)
    name = str_field(data, "name", max_len=100) or None
    if clone_from is not None and not template_exists(clone_from):
        raise ValidationError({"cloneFrom": f"template {clone_from} does not exist"})

    new_no = (Session.query(func.max(_NO)).scalar() or 0) + 1
    if clone_from is None:
        Session.add(
            ProcessTag(processid=1, process="New process", day_range=1, template_no=new_no)
        )
    else:
        for tag in Session.query(ProcessTag).filter(tag_in_template(clone_from)).all():
            Session.add(
                ProcessTag(
                    processid=tag.processid,
                    process=tag.process,
                    day_range=tag.day_range,
                    template_no=new_no,
                )
            )
        for t in Session.query(PTemplate).filter(ptemplate_in_template(clone_from)).all():
            Session.add(
                PTemplate(
                    processid=t.processid,
                    task=t.task,
                    results=t.results,
                    undertaker=t.undertaker,
                    template_no=new_no,
                )
            )
    if name:
        Session.add(TemplateName(template_no=new_no, name=name))
    Session.commit()
    return {"templateNo": new_no, "name": name}, 201


@bp.patch("/templates/<int:no>")
@jwt_required()
def rename_template(no):
    """PATCH /api/templates/<no> — set or clear (blank) the template's name."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    if not template_exists(no):
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    if "name" not in data:
        raise ValidationError({"name": "is required"})
    name = str_field(data, "name", max_len=100)
    row = Session.get(TemplateName, no)
    if name:
        if row:
            row.name = name
        else:
            Session.add(TemplateName(template_no=no, name=name))
    elif row:
        Session.delete(row)
    Session.commit()
    return {"templateNo": no, "name": name or None}


@bp.post("/templates/<int:no>/processes")
@jwt_required()
def create_process(no):
    """POST /api/templates/<no>/processes — append a process (processid = max + 1)."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    if not template_exists(no):
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    next_id = (
        Session.query(func.max(ProcessTag.processid)).filter(tag_in_template(no)).scalar()
        or 0
    ) + 1
    row = ProcessTag(
        processid=next_id,
        process=str_field(data, "process", required=True),
        day_range=int_field(data, "dayRange", default=1, minimum=0),
        template_no=no,
    )
    Session.add(row)
    Session.commit()
    return row.to_dict(), 201


@bp.patch("/process-tags/<int:tid>")
@jwt_required()
def update_process_tag(tid):
    """PATCH /api/process-tags/<tid> — rename a process / change its day budget."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    row = Session.get(ProcessTag, tid)
    if not row:
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    if "process" in data:
        row.process = str_field(data, "process", required=True)
    if "dayRange" in data:
        row.day_range = int_field(data, "dayRange", default=0, minimum=0)
    Session.commit()
    return row.to_dict()


@bp.delete("/process-tags/<int:tid>")
@jwt_required()
def delete_process_tag(tid):
    """DELETE /api/process-tags/<tid> — drop a process and its template tasks.

    Refused (409) for the template's last process: the template would stop
    existing while projects may still reference it.
    """
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    row = Session.get(ProcessTag, tid)
    if not row:
        return _not_found()
    no = _template_no_of(row)
    remaining = (
        Session.query(ProcessTag).filter(tag_in_template(no), ProcessTag.id != tid).count()
    )
    if not remaining:
        return _conflict("A template must keep at least one process")
    (
        Session.query(PTemplate)
        .filter(ptemplate_in_template(no), PTemplate.processid == row.processid)
        .delete(synchronize_session=False)
    )
    Session.delete(row)
    Session.commit()
    return "", 204


@bp.get("/process-tags")
@jwt_required()
def list_process_tags():
    """GET /api/process-tags — list process name lookup rows (process + day_range).

    Optional ``?templateNo=`` narrows to one template.
    """
    q = Session.query(ProcessTag)
    if request.args.get("templateNo", type=int) is not None:
        q = q.filter(tag_in_template(request.args.get("templateNo", type=int)))
    rows = q.order_by(ProcessTag.id.asc()).all()
    return {"items": [r.to_dict() for r in rows]}


# ── Template tasks (ptemplate rows) ───────────────────────────────────────────


@bp.get("/ptemplate")
@jwt_required()
def list_ptemplate():
    """GET /api/ptemplate — list template task rows (``?templateNo=`` narrows).

    Each row gets ``process`` resolved from ``process_tags.process`` by
    (templateNo, processid), so the client sees a readable label per task.
    """
    template_no = request.args.get("templateNo", type=int)
    tag_q = Session.query(ProcessTag)
    row_q = Session.query(PTemplate)
    if template_no is not None:
        tag_q = tag_q.filter(tag_in_template(template_no))
        row_q = row_q.filter(ptemplate_in_template(template_no))
    names = {(_template_no_of(t), t.processid): t.process for t in tag_q.all()}
    rows = row_q.order_by(PTemplate.id.asc()).all()
    return {
        "items": [
            {**r.to_dict(), "process": names.get((_template_no_of(r), r.processid))}
            for r in rows
        ]
    }


def _optional_text(data, key):
    """Free-text field that may be blank: '' normalizes to None."""
    return str_field(data, key) or None


@bp.post("/ptemplate")
@jwt_required()
def create_ptemplate():
    """POST /api/ptemplate — admin-only: add a task row to a template.

    Body: {task, processId, templateNo?=1, results?, undertaker?}. The
    (templateNo, processId) process must exist. Does NOT retroactively seed
    existing projects; only future ``create_project`` calls (and explicit
    ptrack/generate calls) pick up the new row.
    """
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))
    template_no = int_field(data, "templateNo", default=DEFAULT_TEMPLATE_NO, minimum=1)
    processid = int_field(data, "processId")
    if processid is None:
        raise ValidationError({"processId": "is required"})
    exists = (
        Session.query(ProcessTag.id)
        .filter(tag_in_template(template_no), ProcessTag.processid == processid)
        .first()
    )
    if not exists:
        raise ValidationError(
            {"processId": f"process {processid} not found in template {template_no}"}
        )
    row = PTemplate(
        task=str_field(data, "task", required=True),
        processid=processid,
        results=_optional_text(data, "results"),
        undertaker=_optional_text(data, "undertaker"),
        template_no=template_no,
    )
    Session.add(row)
    Session.commit()
    return row.to_dict(), 201


@bp.patch("/ptemplate/<int:tid>")
@jwt_required()
def update_ptemplate(tid):
    """PATCH /api/ptemplate/<tid> — edit a template task (not its process)."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    row = Session.get(PTemplate, tid)
    if not row:
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    if "task" in data:
        row.task = str_field(data, "task", required=True)
    if "results" in data:
        row.results = _optional_text(data, "results")
    if "undertaker" in data:
        row.undertaker = _optional_text(data, "undertaker")
    Session.commit()
    return row.to_dict()


@bp.delete("/ptemplate/<int:tid>")
@jwt_required()
def delete_ptemplate(tid):
    """DELETE /api/ptemplate/<tid> — admin-only: remove a template task row."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    row = Session.get(PTemplate, tid)
    if not row:
        return _not_found()
    Session.delete(row)
    Session.commit()
    return "", 204

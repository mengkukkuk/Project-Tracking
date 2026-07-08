"""Process template lookup resources.

``ptemplate`` rows define the default process/task checklist that is
bulk-inserted into a project's ``ptrack`` on creation. ``process_tags`` is a
lookup of process names. Both are admin-managed reference data; reads are open
to any authenticated user, writes require an admin.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import ProcessTag, PTemplate
from ..validation import int_field, require_dict, str_field
from .helpers import require_permission

bp = Blueprint("ptemplate", __name__, url_prefix="/api")


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


@bp.get("/ptemplate")
@jwt_required()
def list_ptemplate():
    """GET /api/ptemplate — list the default checklist template rows.

    Each row gets ``process`` resolved from ``process_tags.process`` by
    processid, so the client sees a human-readable label per template task.
    """
    tag_names = dict(Session.query(ProcessTag.processid, ProcessTag.process).all())
    rows = Session.query(PTemplate).order_by(PTemplate.id.asc()).all()
    return {
        "items": [
            {**r.to_dict(), "process": tag_names.get(r.processid)} for r in rows
        ]
    }


@bp.post("/ptemplate")
@jwt_required()
def create_ptemplate():
    """POST /api/ptemplate — admin-only: add a row to the default checklist.

    Body: {task, processId}. Does NOT retroactively seed existing projects;
    only future ``create_project`` calls (and explicit ptrack/generate calls)
    pick up the new row.
    """
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))
    row = PTemplate(
        task=str_field(data, "task"),
        processid=int_field(data, "processId"),
    )
    Session.add(row)
    Session.commit()
    return row.to_dict(), 201


@bp.delete("/ptemplate/<int:tid>")
@jwt_required()
def delete_ptemplate(tid):
    """DELETE /api/ptemplate/<tid> — admin-only: remove a default checklist row."""
    denied = require_permission(current_user(), "templates.manage")
    if denied:
        return denied
    row = Session.get(PTemplate, tid)
    if not row:
        return _not_found()
    Session.delete(row)
    Session.commit()
    return "", 204


@bp.get("/process-tags")
@jwt_required()
def list_process_tags():
    """GET /api/process-tags — list process name lookup rows (process + day_range).

    Used by the client to derive the canonical process order and per-group day
    budgets when computing ptrack start/due dates.
    """
    rows = Session.query(ProcessTag).order_by(ProcessTag.id.asc()).all()
    return {"items": [r.to_dict() for r in rows]}

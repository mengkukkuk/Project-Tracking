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

bp = Blueprint("ptemplate", __name__, url_prefix="/api")


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _admin_only(user):
    if user is None or user.role != "admin":
        return {"error": {"type": "http", "code": 403, "message": "Forbidden"}}, 403
    return None


@bp.get("/ptemplate")
@jwt_required()
def list_ptemplate():
    # The process *name* lives in process_tags; join it in by processid so the
    # client gets a human-readable label alongside each template task.
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
    denied = _admin_only(current_user())
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
    denied = _admin_only(current_user())
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
    rows = Session.query(ProcessTag).order_by(ProcessTag.id.asc()).all()
    return {"items": [r.to_dict() for r in rows]}

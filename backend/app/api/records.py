"""Generic per-project record resources.

A single schema-driven blueprint serves CRUD for the auxiliary per-project
tables (process tracking, survey reports, meeting minutes, BOM/costing,
internal verification, exception log). Each resource is described by a small
field spec mapping JSON keys to ORM attributes and validators, so all six
share one set of list/create/update/delete handlers.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import (
    BomAndCosting,
    CustomerMom,
    ExceptionLog,
    InternalVerification,
    ProcessTag,
    Project,
    PTrack,
    SurveyReport,
)
from ..validation import (
    bool_field,
    date_field,
    int_field,
    require_dict,
    str_field,
)
from .helpers import (
    log_activity,
    recompute_project_status,
    recompute_ptrack_dates,
    recompute_ptrack_status,
    require_owner_or_admin,
)

bp = Blueprint("records", __name__, url_prefix="/api")


# --- Field parsers ----------------------------------------------------------
# Each spec entry: (jsonKey, ormAttr, parser) where parser(data, jsonKey) -> value.
def _text(data, key):
    return str_field(data, key)


def _date(data, key):
    return date_field(data, key)


def _int(data, key):
    return int_field(data, key)


def _bool(data, key):
    return bool_field(data, key, default=False)


# --- Resource registry ------------------------------------------------------
RECORD_TYPES = {
    "ptrack": {
        "model": PTrack,
        "label": "process",
        "fields": [
            ("process", "process", _text),
            ("pm", "pm", _text),
            ("startDate", "start_date", _date),
            ("dueDate", "due_date", _date),
            ("task", "task", _text),
            ("status", "status", _text),
            ("checked", "checked", _bool),
            ("reference", "reference", _text),
        ],
        "owns_user": True,
    },
    "survey": {
        "model": SurveyReport,
        "label": "survey report",
        "fields": [
            ("date", "date", _date),
            ("department", "department", _text),
            ("requirement", "requirement", _text),
            ("issue", "issue", _text),
            ("limitation", "limitation", _text),
            ("result", "result", _text),
            ("conclude", "conclude", _text),
            ("surveyor", "surveyor", _text),
        ],
        "owns_user": True,
    },
    "mom": {
        "model": CustomerMom,
        "label": "meeting minutes",
        "fields": [
            ("date", "date", _date),
            ("participant", "participant", _text),
            ("topic", "topic", _text),
            ("concerns", "concerns", _text),
            ("conclude", "conclude", _text),
            ("todo", "todo", _text),
        ],
        "owns_user": True,
    },
    "bom": {
        "model": BomAndCosting,
        "label": "BOM item",
        "fields": [
            ("dateApprove", "date_approve", _date),
            ("category", "category", _text),
            ("categoryId", "category_id", _int),
            ("typeId", "type_id", _int),
            ("deviceName", "device_name", _text),
            ("version", "version", _text),
            ("spec", "spec", _text),
            ("quantity", "quantity", _int),
            ("unit", "unit", _text),
            ("position", "position", _text),
            ("unitPrice", "unit_price", _int),
            ("totalPrice", "total_price", _int),
            ("leadTime", "lead_time", _int),
            ("supplier", "supplier", _text),
        ],
        "owns_user": False,
    },
    "verification": {
        "model": InternalVerification,
        "label": "verification",
        "fields": [
            ("date", "date", _date),
            ("approver", "approver", _text),
            ("testSystem", "test_system", _text),
            ("testResult", "test_result", _text),
            ("defected", "defected", _text),
            ("solution", "solution", _text),
            ("status", "status", _bool),
        ],
        "owns_user": True,
    },
    "exceptions": {
        "model": ExceptionLog,
        "label": "exception",
        "fields": [
            ("date", "date", _date),
            ("informer", "informer", _text),
            ("orderList", "order_list", _text),
            ("effectPrice", "effect_price", _text),
            ("effectTech", "effect_tech", _text),
            ("dateNewBom", "date_new_bom", _date),
            ("dateNewPps", "date_new_pps", _date),
        ],
        "owns_user": False,
    },
}


def _spec(resource):
    return RECORD_TYPES.get(resource)


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _apply(record, spec, data, *, partial):
    """Assign field values from request data onto the ORM record."""
    for json_key, attr, parser in spec["fields"]:
        if partial and json_key not in data:
            continue
        setattr(record, attr, parser(data, json_key))


@bp.get("/bom/all")
@jwt_required()
def list_all_bom():
    """GET /api/bom/all — every BOM/costing row across all projects.

    Powers the global BOM page. Each item is the row's ``to_dict()`` (which
    already carries ``projectId``) enriched with ``projectName`` from a join to
    ``projects`` so the client can show which project a record belongs to.
    Available to any authenticated user, mirroring the per-project BOM tab.
    """
    rows = (
        Session.query(BomAndCosting, Project.name)
        .join(Project, BomAndCosting.project_id == Project.id)
        .order_by(Project.name.asc(), BomAndCosting.id.asc())
        .all()
    )
    items = [{**rec.to_dict(), "projectName": project_name} for rec, project_name in rows]
    return {"items": items}


@bp.get("/projects/<int:pid>/records/<resource>")
@jwt_required()
def list_records(pid, resource):
    """GET /api/projects/<pid>/records/<resource> — list rows for one record type.

    ``<resource>`` is one of :data:`RECORD_TYPES` (ptrack, survey, mom, bom,
    verification, exceptions). For ``ptrack`` only: refreshes the persisted
    date chain via ``recompute_ptrack_dates`` and enriches each row with
    ``dayRange`` + ``cumulativeDays`` from ``process_tags`` so the client can
    derive per-group start/due dates relative to the project's startDate.
    """
    spec = _spec(resource)
    if not spec:
        return _not_found()
    if not Session.get(Project, pid):
        return _not_found()
    # Keep ptrack dates + per-process status persisted on the DB rows in sync
    # with the chain derived from process_tags.day_range and the project's
    # start_date, and with the latest checkbox state.
    if resource == "ptrack":
        recompute_ptrack_dates(pid)
        recompute_ptrack_status(pid)
    model = spec["model"]
    rows = (
        Session.query(model)
        .filter(model.project_id == pid)
        .order_by(model.id.asc())
        .all()
    )
    items = [r.to_dict() for r in rows]

    # For ptrack: enrich each row with the day_range from process_tags
    # plus a running cumulative offset across the canonical process order
    # (process_tags.processid asc). The client derives per-group due dates as
    #   due_date  = project.start_date + cumulativeDays
    #   start_date = previous group's due_date + 1 (first group: project.start_date)
    if resource == "ptrack" and items:
        tag_rows = (
            Session.query(ProcessTag.process, ProcessTag.day_range)
            .order_by(ProcessTag.processid.asc())
            .all()
        )
        cumulative_by_name = {}
        running = 0
        for name, dr in tag_rows:
            running += int(dr or 0)
            cumulative_by_name[name] = (int(dr or 0), running)
        for it in items:
            dr, cum = cumulative_by_name.get(it.get("process"), (None, None))
            it["dayRange"] = dr
            it["cumulativeDays"] = cum

    return {"items": items}


@bp.post("/projects/<int:pid>/records/<resource>")
@jwt_required()
def create_record(pid, resource):
    """POST /api/projects/<pid>/records/<resource> — insert one record.

    Body keys are validated by the resource's field spec in :data:`RECORD_TYPES`.
    For specs flagged ``owns_user``, the row also captures ``user_id`` from the
    JWT for later attribution. Logs a ``task`` activity on the parent project.
    """
    spec = _spec(resource)
    if not spec:
        return _not_found()
    if not Session.get(Project, pid):
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    user = current_user()
    record = spec["model"](project_id=pid)
    if spec["owns_user"]:
        record.user_id = user.id if user else None
    _apply(record, spec, data, partial=False)
    Session.add(record)
    log_activity(pid, "task", f"Added {spec['label']}", user)
    Session.commit()
    if resource == "ptrack":
        recompute_project_status(pid)
    return record.to_dict(), 201


@bp.patch("/records/<resource>/<int:rid>")
@jwt_required()
def update_record(resource, rid):
    """PATCH /api/records/<resource>/<rid> — partial update of one record.

    Any authenticated user may edit; only fields present in the body change
    (``partial=True``). Used by the process checklist for the optimistic
    toggle on ptrack.checked.
    """
    spec = _spec(resource)
    if not spec:
        return _not_found()
    record = Session.get(spec["model"], rid)
    if not record:
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    _apply(record, spec, data, partial=True)
    # BOM rows live in the cross-project global view, so editing one may reparent
    # it to a different project. project_id is intentionally kept out of the
    # generic field spec (other resources aren't movable); handle it here, and
    # reject a target project that doesn't exist before writing the FK.
    if resource == "bom" and "projectId" in data:
        new_pid = int_field(data, "projectId")
        if new_pid is None or not Session.get(Project, new_pid):
            return _not_found()
        record.project_id = new_pid
    Session.commit()
    # Toggling a ptrack checkbox can flip the whole process group's status;
    # refresh persisted status for the parent project so the DB stays in sync.
    # Also re-derive the project's pipeline stage from the new completion %.
    if resource == "ptrack":
        recompute_ptrack_status(record.project_id)
        recompute_project_status(record.project_id)
    return record.to_dict()


@bp.delete("/records/<resource>/<int:rid>")
@jwt_required()
def delete_record(resource, rid):
    """DELETE /api/records/<resource>/<rid> — parent project's owner or admin only."""
    spec = _spec(resource)
    if not spec:
        return _not_found()
    record = Session.get(spec["model"], rid)
    if not record:
        return _not_found()
    user = current_user()
    project = Session.get(Project, record.project_id)
    denied = require_owner_or_admin(user, project.owner_id if project else None)
    if denied:
        return denied
    project_id = record.project_id
    Session.delete(record)
    Session.commit()
    if resource == "ptrack":
        recompute_project_status(project_id)
    return "", 204

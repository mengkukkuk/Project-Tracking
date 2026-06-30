"""Saved BOM lists — named subsets of bom_and_costing rows for a target project.

A BomList is owned by its creator, scoped to a single target project, and
references existing bom_and_costing rows by FK (no snapshotting). Cross-project
items are allowed: a list for Project Alpha may include rows originally entered
under Project Beta.

Authz:
    GET     — any authenticated user
    POST    — any authenticated user (creator becomes owner)
    PATCH   — owner or admin
    DELETE  — owner or admin
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import BomAndCosting, BomList, BomListItem, Project
from ..validation import require_dict, str_field
from .helpers import log_activity, require_owner_or_admin

bp = Blueprint("bom_lists", __name__, url_prefix="/api")


# --- Serialization ---------------------------------------------------------
def _serialize_summary(lst, project_name):
    return {**lst.to_dict(), "projectName": project_name}


def _serialize_detail(lst, project_name):
    """Detail form: include items[] with each underlying BOM row + its source
    project name (mirrors the /api/bom/all enrichment).
    """
    # Bulk-resolve project names for every item's source project in one query.
    src_project_ids = {it.bom.project_id for it in lst.items if it.bom is not None}
    src_names = {}
    if src_project_ids:
        for pid, pname in (
            Session.query(Project.id, Project.name)
            .filter(Project.id.in_(src_project_ids))
            .all()
        ):
            src_names[pid] = pname

    items = []
    for it in lst.items:
        bom = it.bom
        if bom is None:
            continue
        items.append({**bom.to_dict(), "projectName": src_names.get(bom.project_id)})
    return {**_serialize_summary(lst, project_name), "items": items}


# --- Helpers ---------------------------------------------------------------
def _resolve_project(pid):
    """Return Project for an incoming projectId, raising via 422 dict if missing."""
    project = Session.get(Project, pid) if pid is not None else None
    return project


def _validate_item_ids(raw):
    """Coerce body["itemIds"] -> a deduped list of ints. Returns (ids, error_msg)."""
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "itemIds must be a list of integers"
    ids = []
    seen = set()
    for v in raw:
        try:
            i = int(v)
        except (TypeError, ValueError):
            return None, "itemIds must contain only integers"
        if i in seen:
            continue
        seen.add(i)
        ids.append(i)
    return ids, None


def _ensure_boms_exist(ids):
    """Return (missing_ids, ok). 422 if any id has no matching bom_and_costing."""
    if not ids:
        return [], True
    found = {
        row[0]
        for row in Session.query(BomAndCosting.id)
        .filter(BomAndCosting.id.in_(ids))
        .all()
    }
    missing = [i for i in ids if i not in found]
    return missing, not missing


def _replace_items(lst, ids):
    """Replace the list's items with the given ordered bom_ids (in order)."""
    lst.items.clear()
    Session.flush()
    for bid in ids:
        lst.items.append(BomListItem(bom_id=bid))


# --- Endpoints -------------------------------------------------------------
@bp.get("/bom-lists")
@jwt_required()
def list_bom_lists():
    """All saved lists, newest first. Summary form (no items[])."""
    rows = (
        Session.query(BomList, Project.name)
        .outerjoin(Project, BomList.project_id == Project.id)
        .order_by(BomList.updated_at.desc(), BomList.id.desc())
        .all()
    )
    return {"items": [_serialize_summary(lst, pname) for lst, pname in rows]}


@bp.get("/bom-lists/<int:lid>")
@jwt_required()
def get_bom_list(lid):
    lst = Session.get(BomList, lid)
    if not lst:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    project = Session.get(Project, lst.project_id) if lst.project_id else None
    return _serialize_detail(lst, project.name if project else None)


@bp.post("/bom-lists")
@jwt_required()
def create_bom_list():
    data = require_dict(request.get_json(silent=True))
    name = str_field(data, "name", required=True, max_len=200)
    project_id = data.get("projectId")
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return {
            "error": {"type": "validation", "fields": {"projectId": "required"}}
        }, 422
    project = _resolve_project(project_id)
    if project is None:
        return {
            "error": {"type": "validation", "fields": {"projectId": "unknown project"}}
        }, 422

    ids, err = _validate_item_ids(data.get("itemIds"))
    if err:
        return {"error": {"type": "validation", "fields": {"itemIds": err}}}, 422
    missing, ok = _ensure_boms_exist(ids)
    if not ok:
        return {
            "error": {
                "type": "validation",
                "fields": {"itemIds": f"unknown bom id(s): {missing}"},
            }
        }, 422

    user = current_user()
    lst = BomList(
        name=name, project_id=project_id, owner_id=user.id if user else None
    )
    Session.add(lst)
    Session.flush()  # assign lst.id before adding items
    _replace_items(lst, ids)
    log_activity(
        project_id, "task", f"Created BOM list '{name}' ({len(ids)} item(s))", user
    )
    Session.commit()
    return _serialize_summary(lst, project.name), 201


@bp.patch("/bom-lists/<int:lid>")
@jwt_required()
def update_bom_list(lid):
    lst = Session.get(BomList, lid)
    if not lst:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    denied = require_owner_or_admin(user, lst.owner_id)
    if denied:
        return denied

    data = require_dict(request.get_json(silent=True))

    if "name" in data:
        lst.name = str_field(data, "name", required=True, max_len=200)

    if "projectId" in data:
        try:
            new_pid = int(data["projectId"])
        except (TypeError, ValueError):
            return {
                "error": {"type": "validation", "fields": {"projectId": "must be int"}}
            }, 422
        if _resolve_project(new_pid) is None:
            return {
                "error": {
                    "type": "validation",
                    "fields": {"projectId": "unknown project"},
                }
            }, 422
        lst.project_id = new_pid

    if "itemIds" in data:
        ids, err = _validate_item_ids(data["itemIds"])
        if err:
            return {"error": {"type": "validation", "fields": {"itemIds": err}}}, 422
        missing, ok = _ensure_boms_exist(ids)
        if not ok:
            return {
                "error": {
                    "type": "validation",
                    "fields": {"itemIds": f"unknown bom id(s): {missing}"},
                }
            }, 422
        _replace_items(lst, ids)

    log_activity(lst.project_id, "task", f"Updated BOM list '{lst.name}'", user)
    Session.commit()
    project = Session.get(Project, lst.project_id) if lst.project_id else None
    return _serialize_summary(lst, project.name if project else None)


@bp.delete("/bom-lists/<int:lid>")
@jwt_required()
def delete_bom_list(lid):
    lst = Session.get(BomList, lid)
    if not lst:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    denied = require_owner_or_admin(user, lst.owner_id)
    if denied:
        return denied
    name, project_id = lst.name, lst.project_id
    Session.delete(lst)
    log_activity(project_id, "task", f"Deleted BOM list '{name}'", user)
    Session.commit()
    return "", 204

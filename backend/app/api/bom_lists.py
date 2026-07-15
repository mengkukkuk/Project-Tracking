"""Saved BOM lists — named selections of inventory catalogue entries.

A BomList is owned by its creator, scoped to a single target project, and
references ``inventory`` entries by FK (no snapshotting) together with a
per-item quantity. Because the catalogue is project-independent, any list may
draw on any entry; repricing an entry flows through to every list on next read.

``totalPrice`` is derived (quantity x unitPrice) and never stored.

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
from ..models import BomList, BomListItem, Inventory, Project
from ..validation import require_dict, str_field
from .helpers import log_activity, require_owner_or_admin

bp = Blueprint("bom_lists", __name__, url_prefix="/api")


# --- Serialization ---------------------------------------------------------
def _serialize_summary(lst, project_name):
    return {**lst.to_dict(), "projectName": project_name}


def _serialize_detail(lst, project_name):
    """Detail form: include items[] with each catalogue entry + qty and total.

    No project enrichment here (unlike /api/bom/all): a catalogue entry is
    project-independent, so the only project in play is the list's own target.
    """
    items = []
    for it in lst.items:
        inv = it.inventory
        if inv is None:
            continue
        qty = it.quantity
        unit_price = inv.unit_price
        # Derived, never stored. An unpriced entry yields no total rather than
        # a misleading zero.
        total = None if unit_price is None or qty is None else qty * unit_price
        items.append({**inv.to_dict(), "quantity": qty, "totalPrice": total})
    return {**_serialize_summary(lst, project_name), "items": items}


# --- Helpers ---------------------------------------------------------------
def _resolve_project(pid):
    """Return Project for an incoming projectId, raising via 422 dict if missing."""
    project = Session.get(Project, pid) if pid is not None else None
    return project


def _validate_items(raw):
    """Coerce body["items"] -> a deduped [(inventory_id, quantity)].

    Each entry is ``{"inventoryId": int, "quantity": int >= 1}``; quantity is
    optional and defaults to 1. Duplicate inventoryIds collapse (last quantity
    wins) since (list_id, inventory_id) is the composite PK.

    Returns (pairs, error_msg).
    """
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, "items must be a list of {inventoryId, quantity} objects"

    by_id = {}
    order = []
    for entry in raw:
        if not isinstance(entry, dict):
            return None, "items must contain only {inventoryId, quantity} objects"
        try:
            inv_id = int(entry["inventoryId"])
        except (KeyError, TypeError, ValueError):
            return None, "each item needs an integer inventoryId"

        qty_raw = entry.get("quantity", 1)
        if qty_raw is None:
            qty_raw = 1
        try:
            qty = int(qty_raw)
        except (TypeError, ValueError):
            return None, "quantity must be an integer"
        if qty < 1:
            return None, "quantity must be at least 1"

        if inv_id not in by_id:
            order.append(inv_id)
        by_id[inv_id] = qty

    return [(i, by_id[i]) for i in order], None


def _ensure_inventory_exists(pairs):
    """Return (missing_ids, ok). 422 if any id has no matching inventory row."""
    if not pairs:
        return [], True
    ids = [i for i, _ in pairs]
    found = {
        row[0]
        for row in Session.query(Inventory.id).filter(Inventory.id.in_(ids)).all()
    }
    missing = [i for i in ids if i not in found]
    return missing, not missing


def _replace_items(lst, pairs):
    """Replace the list's items with the given (inventory_id, quantity) pairs.

    Callers must send the FULL desired set: this clears and rebuilds, so a
    partial payload silently drops the omitted items.
    """
    lst.items.clear()
    Session.flush()
    for inv_id, qty in pairs:
        lst.items.append(BomListItem(inventory_id=inv_id, quantity=qty))


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

    pairs, err = _validate_items(data.get("items"))
    if err:
        return {"error": {"type": "validation", "fields": {"items": err}}}, 422
    missing, ok = _ensure_inventory_exists(pairs)
    if not ok:
        return {
            "error": {
                "type": "validation",
                "fields": {"items": f"unknown inventory id(s): {missing}"},
            }
        }, 422

    user = current_user()
    lst = BomList(
        name=name, project_id=project_id, owner_id=user.id if user else None
    )
    Session.add(lst)
    Session.flush()  # assign lst.id before adding items
    _replace_items(lst, pairs)
    log_activity(
        project_id, "task", f"Created BOM list '{name}' ({len(pairs)} item(s))", user
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

    # An absent "items" key leaves the existing rows (and their quantities)
    # untouched -- a rename must never disturb the list's contents.
    if "items" in data:
        pairs, err = _validate_items(data["items"])
        if err:
            return {"error": {"type": "validation", "fields": {"items": err}}}, 422
        missing, ok = _ensure_inventory_exists(pairs)
        if not ok:
            return {
                "error": {
                    "type": "validation",
                    "fields": {"items": f"unknown inventory id(s): {missing}"},
                }
            }, 422
        _replace_items(lst, pairs)

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

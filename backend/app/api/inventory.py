"""Inventory catalogue (device price book): the shared pool of devices that
saved BOM lists reference and the BOM page's inventory view manages.

The catalogue is small, so GET returns the whole thing in one payload and the
client filters. Writes are capability-gated (no owner column, so there is no
ownership scope): any authenticated user may add an entry
(``inventory.create``); repricing or deleting a shared entry is elevated-only
(``inventory.update`` / ``inventory.delete``). Deleting an entry cascades out
of ``bom_list_items``, silently shrinking any saved list that references it.
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Inventory
from ..validation import int_field, require_dict, str_field
from .helpers import require_permission

bp = Blueprint("inventory", __name__, url_prefix="/api")


# (jsonKey, ormAttr, parser) — mirrors records.py's spec style. categoryId /
# typeId are int-coerced only, not existence-checked against the lookup
# tables (parity with the bom record spec).
_FIELDS = [
    ("categoryId", "category_id", lambda d, k: int_field(d, k)),
    ("typeId", "type_id", lambda d, k: int_field(d, k)),
    ("deviceName", "device_name", lambda d, k: str_field(d, k)),
    ("version", "version", lambda d, k: str_field(d, k)),
    ("spec", "spec", lambda d, k: str_field(d, k)),
    ("unit", "unit", lambda d, k: str_field(d, k)),
    ("unitPrice", "unit_price", lambda d, k: int_field(d, k, minimum=0)),
    ("supplier", "supplier", lambda d, k: str_field(d, k)),
    ("leadTime", "lead_time", lambda d, k: int_field(d, k, minimum=0)),
]


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _apply(row, data, *, partial):
    for json_key, attr, parser in _FIELDS:
        if partial and json_key not in data:
            continue
        setattr(row, attr, parser(data, json_key))


@bp.get("/inventory")
@jwt_required()
def list_inventory():
    """GET /api/inventory -> {"items": [...]} ordered by device name.

    ``Inventory.category_ref``/``type_ref`` are lazy="joined", so the taxonomy
    labels resolve in this one query rather than N+1.
    """
    rows = Session.query(Inventory).order_by(Inventory.device_name.asc()).all()
    return {"items": [r.to_dict() for r in rows]}


@bp.post("/inventory")
@jwt_required()
def create_inventory():
    """POST /api/inventory — add a catalogue entry.

    Device name is the only required field; everything else is optional.
    Unknown body keys are silently ignored (same as the record resources).
    """
    denied = require_permission(current_user(), "inventory.create")
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))
    str_field(data, "deviceName", required=True)
    row = Inventory()
    _apply(row, data, partial=False)
    Session.add(row)
    Session.commit()
    return row.to_dict(), 201


@bp.patch("/inventory/<int:iid>")
@jwt_required()
def update_inventory(iid):
    """PATCH /api/inventory/<iid> — partial update; elevated roles only."""
    denied = require_permission(current_user(), "inventory.update")
    if denied:
        return denied
    row = Session.get(Inventory, iid)
    if not row:
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    # deviceName stays the one required field: a PATCH may omit it but must
    # not blank it.
    if "deviceName" in data:
        str_field(data, "deviceName", required=True)
    _apply(row, data, partial=True)
    Session.commit()
    return row.to_dict()


@bp.delete("/inventory/<int:iid>")
@jwt_required()
def delete_inventory(iid):
    """DELETE /api/inventory/<iid> — elevated roles only.

    ``bom_list_items.inventory_id`` is ON DELETE CASCADE, so the entry also
    disappears from every saved BOM list that referenced it.
    """
    denied = require_permission(current_user(), "inventory.delete")
    if denied:
        return denied
    row = Session.get(Inventory, iid)
    if not row:
        return _not_found()
    Session.delete(row)
    Session.commit()
    return "", 204

"""Supplier directory (``pjtrk.supplier``): small table, one payload,
client-side matching — same read contract as /api/lookups.

Writes are admin-gated (``suppliers.create`` / ``suppliers.update`` — see
``app/permissions.py``): the supplier profile is shared reference data with no
owner column, so there is no ownership scope to narrow, only a capability
gate. There is no delete endpoint (not needed yet).
"""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Supplier
from ..validation import require_dict, str_field
from .helpers import require_permission

bp = Blueprint("suppliers", __name__, url_prefix="/api")

# (jsonKey, ormAttr) — plain str fields, no numeric/enum types on this model.
_FIELDS = [
    ("name", "sup_name"),
    ("code", "sup_code"),
    ("description", "description"),
    ("address", "address"),
    ("mobile", "mobile"),
    ("telephone", "telephone"),
    ("email", "email"),
    ("lineAcc", "lineacc"),
    ("website", "website"),
    ("taxId", "tax_id"),
]


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _apply(row, data, *, partial):
    for json_key, attr in _FIELDS:
        if partial and json_key not in data:
            continue
        setattr(row, attr, str_field(data, json_key))


@bp.get("/suppliers")
@jwt_required()
def list_suppliers():
    """GET /api/suppliers -> {"items": [...]} ordered by name."""
    rows = Session.query(Supplier).order_by(Supplier.sup_name.asc()).all()
    return {"items": [r.to_dict() for r in rows]}


@bp.post("/suppliers")
@jwt_required()
def create_supplier():
    """POST /api/suppliers — admin-only. Supplier name is the only required field."""
    denied = require_permission(current_user(), "suppliers.create")
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))
    str_field(data, "name", required=True)
    row = Supplier()
    _apply(row, data, partial=False)
    Session.add(row)
    Session.commit()
    return row.to_dict(), 201


@bp.patch("/suppliers/<int:sid>")
@jwt_required()
def update_supplier(sid):
    """PATCH /api/suppliers/<sid> — admin-only partial update.

    Name stays the one required field: a PATCH may omit it but must not
    blank it (mirrors inventory's deviceName rule).
    """
    denied = require_permission(current_user(), "suppliers.update")
    if denied:
        return denied
    row = Session.get(Supplier, sid)
    if not row:
        return _not_found()
    data = require_dict(request.get_json(silent=True))
    if "name" in data:
        str_field(data, "name", required=True)
    _apply(row, data, partial=True)
    Session.commit()
    return row.to_dict()

"""Read-only reference data: the inventory catalogue (device price book).

Backs the saved-BOM-list picker, which builds a list by choosing catalogue
entries and a quantity for each. The catalogue is small, so the whole thing is
returned in one payload and filtered client-side.

Read-only by design: entries are managed via SQL/seed, not the API. There is
deliberately no POST/PATCH/DELETE here.
"""
from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import Session
from ..models import Inventory

bp = Blueprint("inventory", __name__, url_prefix="/api")


@bp.get("/inventory")
@jwt_required()
def list_inventory():
    """GET /api/inventory -> {"items": [...]} ordered by device name.

    ``Inventory.category_ref``/``type_ref`` are lazy="joined", so the taxonomy
    labels resolve in this one query rather than N+1.
    """
    rows = Session.query(Inventory).order_by(Inventory.device_name.asc()).all()
    return {"items": [r.to_dict() for r in rows]}

"""Read-only reference data: the supplier directory (``pjtrk.supplier``).

Small table, one payload, client-side matching — same contract as /api/lookups.
Rows are maintained directly in the DB; there are no write endpoints.
"""
from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import Session
from ..models import Supplier

bp = Blueprint("suppliers", __name__, url_prefix="/api")


@bp.get("/suppliers")
@jwt_required()
def list_suppliers():
    """GET /api/suppliers -> {"items": [...]} ordered by name."""
    rows = Session.query(Supplier).order_by(Supplier.sup_name.asc()).all()
    return {"items": [r.to_dict() for r in rows]}

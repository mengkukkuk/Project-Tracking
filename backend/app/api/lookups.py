"""Read-only reference data: the lookup_type / lookup_value taxonomy.

Powers the BOM page's Category -> Type cascading filter. The whole (small)
taxonomy is returned in one nested payload so the client can cascade
Category -> Type entirely client-side, with no per-selection round-trip.
"""
from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import Session
from ..models import LookupType, LookupValue

bp = Blueprint("lookups", __name__, url_prefix="/api")


@bp.get("/lookups")
@jwt_required()
def list_lookups():
    """GET /api/lookups -> nested {"types": [{..., "values": [...]}]}.

    Active types ordered by name, each carrying its active values ordered by
    display_name. Two queries total (no N+1): one for types, one for all
    values grouped in Python by their parent type.
    """
    types = (
        Session.query(LookupType)
        .filter(LookupType.is_active.is_(True))
        .order_by(LookupType.name.asc())
        .all()
    )
    values = (
        Session.query(LookupValue)
        .filter(LookupValue.is_active.is_(True))
        .order_by(LookupValue.display_name.asc())
        .all()
    )
    values_by_type = {}
    for v in values:
        values_by_type.setdefault(v.lookup_type_id, []).append(v.to_dict())

    items = [
        {**t.to_dict(), "values": values_by_type.get(t.id, [])} for t in types
    ]
    return {"types": items}

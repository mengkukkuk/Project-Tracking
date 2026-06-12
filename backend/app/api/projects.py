"""Projects resource: list (with filtering/search/sort/pagination) and CRUD."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy import or_

from ..auth import current_user
from ..extensions import Session
from ..models import Project, Tag
from ..validation import (
    ValidationError,
    date_field,
    int_field,
    number_field,
    priority_field,
    require_dict,
    status_field,
    str_field,
)
from .helpers import log_activity, require_owner_or_admin

bp = Blueprint("projects", __name__, url_prefix="/api/projects")

SORTABLE = {
    "name": Project.name,
    "value": Project.value,
    "progress": Project.progress,
    "status": Project.status,
    "priority": Project.priority,
    "updatedAt": Project.updated_at,
    "createdAt": Project.created_at,
    "dueDate": Project.due_date,
}


def _resolve_tags(names):
    """Map a list of tag names to Tag rows, creating any that don't exist."""
    tags = []
    for raw in names or []:
        name = str(raw).strip()
        if not name:
            continue
        if len(name) > 48:
            raise ValidationError({"tags": f"tag name must be at most 48 characters: '{name[:20]}...'"})
        tag = Session.query(Tag).filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            Session.add(tag)
            Session.flush()
        tags.append(tag)
    return tags


@bp.get("")
@jwt_required()
def list_projects():
    q = Session.query(Project)

    # --- Filtering ---
    status = request.args.get("status")
    if status:
        q = q.filter(Project.status == status)
    domain = request.args.get("domain")
    if domain:
        q = q.filter(Project.domain == domain)
    priority = request.args.get("priority")
    if priority:
        q = q.filter(Project.priority == priority)
    fiscal_year = request.args.get("fiscalYear")
    if fiscal_year:
        q = q.filter(Project.fiscal_year == fiscal_year)

    # --- Full-text-ish search ---
    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                Project.name.ilike(like),
                Project.customer.ilike(like),
                Project.pm.ilike(like),
                Project.description.ilike(like),
            )
        )

    total = q.count()

    # --- Sorting ---
    sort = request.args.get("sort", "updatedAt")
    col = SORTABLE.get(sort, Project.updated_at)
    if request.args.get("dir", "desc") == "asc":
        q = q.order_by(col.asc())
    else:
        q = q.order_by(col.desc())

    # --- Pagination (opt-in; returns everything by default for the SPA) ---
    page = max(1, int_field(request.args, "page", default=1) or 1)
    per_page = int_field(request.args, "perPage", default=0) or 0
    if per_page > 0:
        q = q.limit(per_page).offset((page - 1) * per_page)

    rows = q.all()
    return {
        "items": [r.to_dict() for r in rows],
        "total": total,
        "page": page,
        "perPage": per_page,
    }


@bp.get("/<int:pid>")
@jwt_required()
def get_project(pid):
    p = Session.get(Project, pid)
    if not p:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    return p.to_dict(detail=True)


@bp.post("")
@jwt_required()
def create_project():
    data = require_dict(request.get_json(silent=True))
    user = current_user()
    p = Project(
        name=str_field(data, "name", required=True, max_len=255),
        description=str_field(data, "description"),
        domain=str_field(data, "domain", max_len=64),
        customer=str_field(data, "customer", max_len=255),
        pm=str_field(data, "pm", max_len=128),
        status=status_field(data, default="Pre-Sale"),
        priority=priority_field(data, default="medium"),
        value=number_field(data, "value", default=0, minimum=0),
        progress=int_field(data, "progress", default=0, minimum=0, maximum=100),
        fiscal_year=str_field(data, "fiscalYear", default="future", max_len=8),
        start_date=date_field(data, "startDate"),
        due_date=date_field(data, "dueDate"),
        owner_id=user.id if user else None,
    )
    p.tags = _resolve_tags(data.get("tags"))
    Session.add(p)
    Session.flush()
    log_activity(p.id, "created", f"Created project “{p.name}”", user)
    Session.commit()
    return p.to_dict(detail=True), 201


@bp.patch("/<int:pid>")
@jwt_required()
def update_project(pid):
    p = Session.get(Project, pid)
    if not p:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    denied = require_owner_or_admin(user, p.owner_id)
    if denied:
        return denied
    data = require_dict(request.get_json(silent=True))

    changes = []
    if "name" in data:
        p.name = str_field(data, "name", required=True, max_len=255)
    if "description" in data:
        p.description = str_field(data, "description")
    if "domain" in data:
        p.domain = str_field(data, "domain", max_len=64)
    if "customer" in data:
        p.customer = str_field(data, "customer", max_len=255)
    if "pm" in data:
        p.pm = str_field(data, "pm", max_len=128)
    if "status" in data:
        new_status = status_field(data, required=True)
        if new_status != p.status:
            changes.append(f"status → {new_status}")
            log_activity(p.id, "moved", f"{p.status} → {new_status}", user)
        p.status = new_status
    if "priority" in data:
        p.priority = priority_field(data, required=True)
    if "value" in data:
        p.value = number_field(data, "value", default=0, minimum=0)
    if "progress" in data:
        p.progress = int_field(data, "progress", default=0, minimum=0, maximum=100)
    if "fiscalYear" in data:
        p.fiscal_year = str_field(data, "fiscalYear", max_len=8)
    if "startDate" in data:
        p.start_date = date_field(data, "startDate")
    if "dueDate" in data:
        p.due_date = date_field(data, "dueDate")
    if "tags" in data:
        p.tags = _resolve_tags(data.get("tags"))

    if changes:
        log_activity(p.id, "updated", "; ".join(changes), user)
    Session.commit()
    return p.to_dict(detail=True)


@bp.delete("/<int:pid>")
@jwt_required()
def delete_project(pid):
    p = Session.get(Project, pid)
    if not p:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    denied = require_owner_or_admin(user, p.owner_id)
    if denied:
        return denied
    Session.delete(p)
    Session.commit()
    return "", 204

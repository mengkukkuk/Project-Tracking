"""Server-side dashboard aggregations.

The SPA can derive most of these from the project list, but exposing them here
keeps heavy dashboards cheap and lets non-SPA clients (reports, exports) reuse
the same numbers.

Aggregations run entirely in SQL to avoid loading all project rows into Python.
"""
from datetime import date, timedelta

from flask import Blueprint
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ..extensions import Session
from ..models import PRIORITIES, STAGES, Project

bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@bp.get("")
@jwt_required()
def stats():
    """GET /api/stats — dashboard aggregations.

    Returns scalar totals, funnel counts/value per status, fiscal-year x status
    matrix, by-domain and by-priority counts, overdue count, and an upcoming
    list (LIMIT 8 in SQL). All numbers computed via ``GROUP BY`` to avoid
    pulling all project rows into Python.
    """
    today = date.today()
    soon = today + timedelta(days=14)

    # --- Scalar aggregates ---
    total, total_value, avg_progress = Session.query(
        func.count(Project.id),
        func.coalesce(func.sum(Project.value), 0),
        func.coalesce(func.avg(Project.progress), 0),
    ).one()
    total_value = float(total_value)
    avg_progress = round(float(avg_progress), 1)

    # --- Funnel: count + value per status ---
    funnel = {s: {"count": 0, "value": 0.0} for s in STAGES}
    for status, cnt, val in Session.query(
        Project.status,
        func.count(Project.id),
        func.coalesce(func.sum(Project.value), 0),
    ).group_by(Project.status).all():
        if status in funnel:
            funnel[status] = {"count": int(cnt), "value": float(val)}

    # --- By fiscal year + status ---
    by_fy: dict = {}
    for fy, status, cnt in Session.query(
        func.coalesce(Project.fiscal_year, "future"),
        Project.status,
        func.count(Project.id),
    ).group_by(Project.fiscal_year, Project.status).all():
        by_fy.setdefault(fy, {s: 0 for s in STAGES})
        if status in STAGES:
            by_fy[fy][status] = int(cnt)

    # --- By domain ---
    by_domain = {
        domain: int(cnt)
        for domain, cnt in Session.query(Project.domain, func.count(Project.id))
        .filter(Project.domain.isnot(None))
        .group_by(Project.domain)
        .all()
    }

    # --- By priority ---
    by_priority = {p: 0 for p in PRIORITIES}
    for priority, cnt in Session.query(
        Project.priority, func.count(Project.id)
    ).group_by(Project.priority).all():
        if priority in by_priority:
            by_priority[priority] = int(cnt)

    # --- Overdue count ---
    overdue = Session.query(func.count(Project.id)).filter(
        Project.due_date < today, Project.status != "Completed"
    ).scalar() or 0

    # --- Upcoming (sorted, limited in SQL) ---
    upcoming_rows = (
        Session.query(Project)
        .filter(
            Project.due_date >= today,
            Project.due_date <= soon,
            Project.status != "Completed",
        )
        .order_by(Project.due_date.asc())
        .limit(8)
        .all()
    )

    completed = funnel["Completed"]["count"]
    total = int(total)
    return {
        "totalProjects": total,
        "totalValue": total_value,
        "pipelineValue": sum(funnel[s]["value"] for s in STAGES[:-1]),
        "wonValue": funnel["Completed"]["value"],
        "inDelivery": funnel["Project Delivery"]["count"],
        "completed": completed,
        "completionRate": round(completed / total * 100, 1) if total else 0,
        "avgProgress": avg_progress,
        "overdue": int(overdue),
        "funnel": [{"stage": s, **funnel[s]} for s in STAGES],
        "byFiscalYear": by_fy,
        "byDomain": by_domain,
        "byPriority": by_priority,
        "upcoming": [r.to_dict() for r in upcoming_rows],
        "stages": STAGES,
    }

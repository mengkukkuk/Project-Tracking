"""Server-side dashboard aggregations.

The SPA can derive most of these from the project list, but exposing them here
keeps heavy dashboards cheap and lets non-SPA clients (reports, exports) reuse
the same numbers.
"""
from datetime import date, timedelta

from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..extensions import Session
from ..models import PRIORITIES, STAGES, Project

bp = Blueprint("stats", __name__, url_prefix="/api/stats")


@bp.get("")
@jwt_required()
def stats():
    rows = Session.query(Project).all()

    funnel = {s: {"count": 0, "value": 0.0} for s in STAGES}
    by_fy = {}
    by_domain = {}
    by_priority = {p: 0 for p in PRIORITIES}
    total_value = 0.0
    overdue = 0
    today = date.today()
    soon = today + timedelta(days=14)
    upcoming = []

    for r in rows:
        val = float(r.value or 0)
        total_value += val

        if r.status in funnel:
            funnel[r.status]["count"] += 1
            funnel[r.status]["value"] += val

        fy = r.fiscal_year or "future"
        by_fy.setdefault(fy, {s: 0 for s in STAGES})
        if r.status in STAGES:
            by_fy[fy][r.status] += 1

        if r.domain:
            by_domain[r.domain] = by_domain.get(r.domain, 0) + 1

        if r.priority in by_priority:
            by_priority[r.priority] += 1

        if r.due_date and r.status != "Completed":
            if r.due_date < today:
                overdue += 1
            elif r.due_date <= soon:
                upcoming.append(r.to_dict())

    upcoming.sort(key=lambda p: p["dueDate"] or "")

    completed = funnel["Completed"]["count"]
    total = len(rows)
    avg_progress = round(sum((r.progress or 0) for r in rows) / total, 1) if total else 0

    return {
        "totalProjects": total,
        "totalValue": total_value,
        "pipelineValue": sum(funnel[s]["value"] for s in STAGES[:-1]),
        "wonValue": funnel["Completed"]["value"],
        "inDelivery": funnel["Project Delivery"]["count"],
        "completed": completed,
        "completionRate": round(completed / total * 100, 1) if total else 0,
        "avgProgress": avg_progress,
        "overdue": overdue,
        "funnel": [{"stage": s, **funnel[s]} for s in STAGES],
        "byFiscalYear": by_fy,
        "byDomain": by_domain,
        "byPriority": by_priority,
        "upcoming": upcoming[:8],
        "stages": STAGES,
    }

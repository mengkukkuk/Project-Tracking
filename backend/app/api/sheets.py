"""Google Sheets integration — export and import projects.

Export: writes all projects to a named tab in the configured spreadsheet.
Import: reads rows from a tab and bulk-creates new projects.

Setup (one-time):
  1. Create a Google Cloud project → enable Sheets API.
  2. Create a Service Account → download the JSON key file.
  3. Share the target spreadsheet with the service account email.
  4. Add to .env:
       GOOGLE_SHEET_ID=<spreadsheet_id_from_url>
       GOOGLE_CREDENTIALS_FILE=/path/to/key.json
       (or GOOGLE_CREDENTIALS_JSON=<raw JSON string>)

Optional:
  GOOGLE_SHEET_TAB=Projects    (default: "Projects")
"""
import json
import os
from datetime import datetime

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Project, Tag
from .helpers import require_permission

bp = Blueprint("sheets", __name__, url_prefix="/api/sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

EXPORT_HEADERS = [
    "ID", "Name", "Domain", "Customer", "PM", "Status", "Priority",
    "Value (THB)", "Progress %", "Fiscal Year", "Start Date", "Due Date",
    "Tags", "Tasks Total", "Tasks Done", "Owner", "Created", "Updated",
]


# ── helpers ────────────────────────────────────────────────────────────────

def _credentials():
    try:
        from google.oauth2 import service_account
    except ImportError:
        raise RuntimeError(
            "google-auth is not installed — "
            "run: pip install google-api-python-client google-auth"
        )
    raw_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    file_path = os.getenv("GOOGLE_CREDENTIALS_FILE")
    if raw_json:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw_json), scopes=SCOPES
        )
    if file_path:
        return service_account.Credentials.from_service_account_file(
            file_path, scopes=SCOPES
        )
    raise RuntimeError(
        "Google credentials not configured — "
        "set GOOGLE_CREDENTIALS_FILE or GOOGLE_CREDENTIALS_JSON in .env"
    )


def _service():
    from googleapiclient.discovery import build
    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def _sheet_id():
    sid = os.getenv("GOOGLE_SHEET_ID", "").strip()
    if not sid:
        raise RuntimeError("GOOGLE_SHEET_ID not set in .env")
    return sid


def _tab():
    return os.getenv("GOOGLE_SHEET_TAB", "Projects")


def _ensure_tab(service, spreadsheet_id, tab_name):
    """Create the tab if it doesn't already exist."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for sheet in meta["sheets"]:
        if sheet["properties"]["title"] == tab_name:
            return
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
    ).execute()


def _project_to_row(p):
    tags = ",".join(t.name for t in (p.tags or []))
    task_total = len(p.tasks) if p.tasks is not None else 0
    task_done = sum(1 for t in (p.tasks or []) if t.done)
    return [
        p.id,
        p.name or "",
        p.domain or "",
        p.customer or "",
        p.pm or "",
        p.status or "",
        p.priority or "",
        float(p.value or 0),
        p.progress or 0,
        p.fiscal_year or "",
        p.start_date.isoformat() if p.start_date else "",
        p.due_date.isoformat() if p.due_date else "",
        tags,
        task_total,
        task_done,
        p.owner.name if p.owner else "",
        p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
        p.updated_at.strftime("%Y-%m-%d %H:%M") if p.updated_at else "",
    ]


def _parse_date(s):
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except Exception:
            pass
    return None


# ── endpoints ──────────────────────────────────────────────────────────────

@bp.get("/status")
@jwt_required()
def status():
    """Return whether Google Sheets is configured (no network call)."""
    configured = bool(
        os.getenv("GOOGLE_CREDENTIALS_FILE") or os.getenv("GOOGLE_CREDENTIALS_JSON")
    ) and bool(os.getenv("GOOGLE_SHEET_ID"))
    return {
        "configured": configured,
        "sheetId": os.getenv("GOOGLE_SHEET_ID") or None,
        "tab": _tab(),
    }


@bp.post("/export")
@jwt_required()
def export_projects():
    """Write all projects to the configured Google Sheet tab (sheets.sync)."""
    denied = require_permission(current_user(), "sheets.sync")
    if denied:
        return denied

    try:
        service = _service()
        sid = _sheet_id()
        tab = _tab()
    except RuntimeError as e:
        return {"error": {"type": "config", "message": str(e)}}, 503

    projects = Session.query(Project).order_by(Project.updated_at.desc()).all()
    rows = [EXPORT_HEADERS] + [_project_to_row(p) for p in projects]

    try:
        _ensure_tab(service, sid, tab)
        service.spreadsheets().values().clear(
            spreadsheetId=sid, range=f"'{tab}'"
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=sid,
            range=f"'{tab}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()
    except Exception as e:
        return {"error": {"type": "sheets", "message": str(e)}}, 502

    return {
        "exported": len(projects),
        "sheetId": sid,
        "tab": tab,
        "url": f"https://docs.google.com/spreadsheets/d/{sid}",
    }


@bp.post("/import")
@jwt_required()
def import_projects():
    """Read rows from the Google Sheet tab and create new projects (admin only).

    Rows whose ID column matches an existing project are skipped (no overwrites).
    Query param ?preview=1 returns what would be created without touching the DB.
    """
    user = current_user()
    denied = require_permission(user, "sheets.sync")
    if denied:
        return denied

    preview = request.args.get("preview", "0") == "1"

    try:
        service = _service()
        sid = _sheet_id()
        tab = _tab()
    except RuntimeError as e:
        return {"error": {"type": "config", "message": str(e)}}, 503

    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sid, range=f"'{tab}'")
            .execute()
        )
    except Exception as e:
        return {"error": {"type": "sheets", "message": str(e)}}, 502

    all_rows = result.get("values", [])
    if not all_rows:
        return {"created": 0, "skipped": 0, "rows": []}

    header = [h.strip() for h in all_rows[0]]
    data_rows = all_rows[1:]

    def cell(row, col_name, fallback=""):
        try:
            idx = header.index(col_name)
            return row[idx] if idx < len(row) else fallback
        except ValueError:
            return fallback

    existing_ids = {row[0] for row in Session.query(Project.id).all()}

    created, skipped = 0, 0
    preview_rows = []

    for row in data_rows:
        if not any(row):
            continue

        try:
            if int(cell(row, "ID")) in existing_ids:
                skipped += 1
                continue
        except (ValueError, TypeError):
            pass  # no ID or non-numeric → treat as new

        name = cell(row, "Name").strip()
        if not name:
            skipped += 1
            continue

        row_data = {
            "name": name,
            "domain": cell(row, "Domain") or None,
            "customer": cell(row, "Customer") or None,
            "pm": cell(row, "PM") or None,
            "status": cell(row, "Status") or "Pre-Sale",
            "priority": cell(row, "Priority") or "medium",
            "value": float(cell(row, "Value (THB)") or 0),
            "progress": int(float(cell(row, "Progress %") or 0)),
            "fiscal_year": cell(row, "Fiscal Year") or "future",
            "start_date": _parse_date(cell(row, "Start Date")),
            "due_date": _parse_date(cell(row, "Due Date")),
        }

        if preview:
            preview_rows.append(row_data)
            created += 1
            continue

        tag_names = [t.strip() for t in cell(row, "Tags", "").split(",") if t.strip()]
        tags = []
        for tag_name in tag_names:
            tag = Session.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                Session.add(tag)
                Session.flush()
            tags.append(tag)

        p = Project(owner_id=user.id, **row_data)
        p.tags = tags
        Session.add(p)
        created += 1

    if not preview:
        Session.commit()

    out = {"created": created, "skipped": skipped, "preview": preview}
    if preview:
        out["rows"] = preview_rows
    return out

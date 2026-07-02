# Project-Tracking
# Last updated 2/7/2026
A full-stack project-tracking application for automation and engineering projects. Built with a **Vue 3 SPA** frontend and a **Flask REST API** backend, with JWT authentication, role-based authorization, CRUD operations, tasks, comments, an activity feed, rich analytics dashboards, and dark mode.

```
┌──────────────────────────────────────────────────────────────┐
│  Vue 3 SPA  (Vite · Pinia · vue-router · ECharts)           │
│   ├─ Auth        JWT login / register · route guard          │
│   ├─ Overview    KPIs · funnel · fiscal bars · domain donut  │
│   │              overdue / upcoming list                      │
│   ├─ Pipeline    Kanban-style board grouped by delivery stage │
│   ├─ PM Cards    board grouped by project manager             │
│   ├─ Kanban      drag-and-drop status (optimistic + rollback) │
│   ├─ Table       sort · filter · search · pagination · CSV   │
│   ├─ BOM Global  cross-project BOM inventory · saved lists ·  │
│   │              Excel import / Excel+PDF export              │
│   ├─ Dashboard   single-project exec report (cost, docs,     │
│   │              process) · per-section Excel/PDF export      │
│   └─ Detail      edit · tasks · process checklist · records  │
│                  comments · activity log                      │
│        │  /api  (Vite proxy in dev)                          │
│        ▼                                                      │
│  Flask REST API  (app factory · blueprints · Flask-Limiter)  │
│   ├─ /api/auth        register · login · me        (JWT)     │
│   ├─ /api/projects    list / filter / search / CRUD          │
│   ├─ /api/projects/:id/tasks · /api/tasks/:id                │
│   ├─ /api/projects/:id/comments · /api/comments/:id          │
│   ├─ /api/projects/:id/records/:resource  (ptrack, bom, ...) │
│   ├─ /api/projects/:id/ptrack/generate  (backfill checklist) │
│   ├─ /api/bom/all     BOM rows across all projects            │
│   ├─ /api/bom-lists   saved named BOM selections   (CRUD)    │
│   ├─ /api/ptemplate   process checklist template             │
│   ├─ /api/sheets      Google Sheets export / import          │
│   ├─ /api/stats       SQL aggregations (no full-table scan)  │
│   └─ /api/users · /api/health                                │
│        ▼                                                      │
│  SQLAlchemy → SQLite (dev) | PostgreSQL | MSSQL              │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # edit DATABASE_URL, SECRET_KEY as needed
python seed.py              # populate demo data  →  admin@scada.local / admin123
python wsgi.py              # http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173  (proxies /api → :5000)
```

Sign in with **admin@scada.local / admin123** (first registered account becomes admin).

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Database

Switch database with a single env variable — no code changes needed:

```bash
# PostgreSQL
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/ProjectTracking

# MSSQL
DATABASE_URL=mssql+pyodbc://user:pass@host/ProjectTracking?driver=ODBC+Driver+18+for+SQL+Server

# SQLite (default — zero config)
DATABASE_URL=sqlite:///project_tracking.db
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite | Connection string |
| `SECRET_KEY` | dev value | Flask secret — **change in production** |
| `JWT_SECRET_KEY` | `SECRET_KEY` | JWT signing key — **change in production** |
| `JWT_HOURS` | `12` | Token lifetime in hours |
| `CORS_ORIGINS` | `""` (same-origin) | `*` for dev, comma-list for prod |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `SEED_ON_START` | `false` | Auto-seed on startup |

## Production

**Frontend** — build and serve the static bundle:

```bash
cd frontend && npm run build
# Serve dist/ via Nginx / IIS
# Set VITE_API_BASE if the API is on a different origin
```

**Backend** — use a production WSGI server:

```bash
# Windows
waitress-serve --port=5000 wsgi:app

# Linux
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
```

Set a strong `SECRET_KEY`, configure `CORS_ORIGINS` to your frontend origin, and use PostgreSQL instead of SQLite.

### Deploy on a new Windows device (Tailscale single-origin)

`backend/start_service.bat` installs both services as NSSM Windows services and
wires a portless HTTPS origin via Tailscale Serve. It is **device-agnostic** — it
derives its own paths from the script location and auto-detects the Tailscale IP,
so no edits are needed per machine.

Prerequisites on the target device: Python 3.11, Node.js, [NSSM](https://nssm.cc),
and [Tailscale](https://tailscale.com) (logged in to your tailnet).

```bat
:: 1. Clone, then create the backend venv + install deps
cd Project-Tracking\backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

:: 2. Configure environment
copy .env.example .env        & rem  edit DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY

:: 3. Initialize the database (PostgreSQL), or rely on SQLite default
::    psql -U postgres -d ProjectTracking -f init_db.sql

:: 4. Install frontend deps
cd ..\frontend & npm install & cd ..\backend

:: 5. Install + start services (run as Administrator)
start_service.bat
```

The script builds the SPA with a **relative `/api` base** and serves everything
under one HTTPS origin, so there is no hardcoded IP and no CORS/mixed-content
config. Final access URL (printed by the script):

```
https://<device-name>.<your-tailnet>.ts.net
```

Manage afterwards: `nssm status ProjTracking`, `tailscale serve status`.

## Architecture Notes

- **Authorization** — admin can do anything; members can only modify their own projects/tasks. Enforced via `require_owner_or_admin()` in [`app/api/helpers.py`](backend/app/api/helpers.py).
- **Rate limiting** — login capped at 10 req/min, register at 5 req/min per IP (Flask-Limiter).
- **Stats** — all aggregations run as SQL `GROUP BY` queries; no full-table Python loops.
- **Kanban** — drag does an optimistic status update with automatic rollback on API failure.
- **Activity feed** — every create / update / status-move is logged per project.
- **Process-driven progress** — the project progress bar is derived from the per-project process checklist (`ptrack`); the same value drives the detail drawer, Table view, and Kanban cards. Falls back to task counts when no checklist exists. Older projects can backfill the checklist on demand via "Generate from template".
- **Per-project records** — each project carries auxiliary records (`ptrack` process checklist, `survey`, `mom` meeting minutes, `bom` bill-of-materials, `verification`, `exceptions`) under `/api/projects/:id/records/:resource`.
- **Record export / import** — every record list supports Excel and PDF export (`frontend/src/utils/recordExport.js`, via `ExcelJS` / `jsPDF`) through the shared `ExportImportMenu` component; the project Table view additionally supports CSV export.
- **BOM Global view** (`/bom`) — a cross-project BOM inventory (`GET /api/bom/all`) with Excel import (maps rows to projects by name or id), Excel/PDF export, and **saved BOM lists** — named, reusable subsets of BOM rows scoped to a target project (`/api/bom-lists`, CRUD).
- **Dashboard view** (`/dashboard`) — a single-project executive report combining cost/procurement insights, document intelligence (survey, verification, MOM, exceptions), and the week-grouped process checklist, each exportable to Excel/PDF.
- **Pipeline / PM Cards views** — read-only Kanban-style boards grouping projects by delivery stage (`/pipeline`) or by project manager (`/pm-cards`), with per-column risk indicators (overdue / critical counts).
- **Google Sheets sync** — `/api/sheets/export` and `/api/sheets/import` round-trip the project list with a configured spreadsheet.
- **Dark mode** — persisted in `localStorage`, respects OS preference on first visit.

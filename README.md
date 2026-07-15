# Project-Tracking
# Last updated 15/7/2026
A full-stack project-tracking application for automation and engineering projects. Built with a **Vue 3 SPA** frontend and a **Flask REST API** backend, with JWT authentication, three-role RBAC (`super_admin`/`admin`/`member`), CRUD operations, tasks, per-project auxiliary records and PDF documents, an inventory catalogue with saved BOM lists, rich analytics dashboards, and dark mode.

```
┌──────────────────────────────────────────────────────────────┐
│  Vue 3 SPA  (Vite · Pinia · vue-router · ECharts)           │
│   ├─ Auth        JWT login / register · route guard          │
│   ├─ Overview    KPIs · funnel · fiscal bars · domain donut  │
│   │              overdue / upcoming list                      │
│   ├─ Pipeline    read-only board grouped by delivery stage    │
│   ├─ PM Cards    read-only board grouped by project manager   │
│   ├─ Table       sort · filter · search · pagination · CSV   │
│   ├─ BOM Global  cross-project BOM · INVENTORY toggle ·       │
│   │              saved lists · Excel import / Excel+PDF export │
│   ├─ Dashboard   single-project exec report (cost, docs,     │
│   │              process) · per-section Excel/PDF export      │
│   ├─ Summaries   4-step calc pipeline: inputs → calcs →       │
│   │              grade + charts, per project + compare-all    │
│   ├─ Users       role + per-user page access (admin+)         │
│   └─ Detail      edit · tasks · process checklist · records  │
│                  documents (PDF) · comments · activity log    │
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
│   ├─ /api/bom-lists   saved lists: inventory refs + qty (CRUD)│
│   ├─ /api/inventory   catalogue (price book), capability-gated│
│   ├─ /api/projects/:id/documents  PDF uploads (quotation/tds/ │
│   │                                result), owner-or-admin    │
│   ├─ /api/ptemplate   process checklist template             │
│   ├─ /api/sheets      Google Sheets export / import          │
│   ├─ /api/stats       SQL aggregations (no full-table scan)  │
│   └─ /api/users · /api/users/:id/role · /api/health          │
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
python wsgi.py               # http://localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173  (proxies /api → :5000)
```

Sign in with **admin@scada.local / admin123** (seeded as `super_admin`; a freshly *registered* account instead becomes plain `admin` — there's no self-service path to `super_admin`).

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest                      # 94 tests — auth, projects, tasks/comments, stats, BOM lists, inventory, documents, RBAC, records
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

> Installs that predate the Summaries pipeline need a one-time `team_size`/`complexity` column migration on an existing `projects` table — see `backend/init_db.sql` or [CLAUDE.md](CLAUDE.md#database) for the exact statement.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and adjust:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite | Connection string (or set `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` individually) |
| `SECRET_KEY` | dev value | Flask secret — **change in production** |
| `JWT_SECRET_KEY` | `SECRET_KEY` | JWT signing key — **change in production** |
| `JWT_HOURS` | `12` | Token lifetime in hours |
| `CORS_ORIGINS` | `""` (same-origin) | `*` for dev, comma-list for prod |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `SEED_ON_START` | `false` | Auto-seed on startup (drops + recreates schema — dev only) |
| `DOCSTORE_DIR` | `backend/docstore` | Where uploaded project PDFs (quotation/tds/result) are stored on disk |
| `MAX_UPLOAD_MB` | `50` | Max multipart upload size in MB (per request) |
| `GOOGLE_SHEET_ID` / `GOOGLE_CREDENTIALS_FILE` / `GOOGLE_CREDENTIALS_JSON` / `GOOGLE_SHEET_TAB` | unset | Optional Google Sheets export/import — see `/api/sheets/*` |
| `NGROK_AUTH_TOKEN` / `NGROK_DOMAIN` | unset | Only used by `backend/install_service.bat` for the Windows single-origin service deploy below |

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

### Deploy on a Windows device as a service (ngrok single-origin)

`backend/install_service.bat` installs **two** NSSM Windows services and wires a
public HTTPS origin via an ngrok tunnel. It is **device-agnostic** — it derives
its own paths from the script location, so no per-machine edits are needed:

- **`ProjTracking`** — Waitress serving the Flask API *and* the built Vue SPA
  from one port (5000), since the frontend is built with a relative `/api`
  base (no CORS, no mixed content).
- **`ProjTrackingNgrok`** — an `ngrok http` tunnel forwarding your reserved
  ngrok domain to port 5000; depends on `ProjTracking`.

Prerequisites on the target device: Python 3.11, Node.js, an
[ngrok](https://ngrok.com) account with a reserved domain and auth token
(`NGROK_AUTH_TOKEN` / `NGROK_DOMAIN`). NSSM and ngrok binaries (`nssm.exe`,
`ngrok.exe`) already ship in `backend/`, so no extra install is needed for
those.

```bat
:: 1. Clone, then create the backend venv + install deps
cd Project-Tracking\backend
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt

:: 2. Configure environment
copy .env.example .env        & rem  edit DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY,
                               & rem  NGROK_AUTH_TOKEN, NGROK_DOMAIN

:: 3. Initialize the database (PostgreSQL), or rely on SQLite default
::    psql -U postgres -d ProjectTracking -f init_db.sql

:: 4. Install frontend deps
cd ..\frontend & npm install & cd ..\backend

:: 5. Install + start both services (run as Administrator)
install_service.bat
```

The script builds the SPA with a relative `/api` base itself (step is
included), so there's nothing to build by hand first. Final access URL
(printed by the script):

```
https://<your-ngrok-domain>
```

Manage afterwards: `nssm status ProjTracking`, `nssm status ProjTrackingNgrok`,
`nssm restart ProjTracking` (after `.env` changes). To remove both services,
run `backend\uninstall_service.bat` (as Administrator).

## Architecture Notes

- **Authorization** — three roles (`super_admin`/`admin`/`member`), split into two axes: **capability** (permission strings in `app/permissions.py`, checked via `require_permission()`) and **scope** (own vs. any record, via `require_owner_or_admin()` in [`app/api/helpers.py`](backend/app/api/helpers.py)). Per-user page access lets a member's side-nav be narrowed below the default full set. See [CLAUDE.md](CLAUDE.md#authorization-model) for the full model.
- **Rate limiting** — login capped at 10 req/min, register at 5 req/min per IP (Flask-Limiter).
- **Stats** — all aggregations run as SQL `GROUP BY` queries; no full-table Python loops.
- **Derived status, no drag-and-drop board** — `status` is not user-editable. It's computed server-side from live progress (`derived_status()` in `app/models.py`) across 5 pipeline stages: Pre-Sale → Project Initiation → award → Project Delivery → Completed. `PipelineView` and `PmCardsView` are read-only boards grouped by this derived status / by PM — there is no Kanban-style drag-to-move view.
- **Activity feed** — every create / update / status-move is logged per project.
- **Process-driven progress** — the project progress bar is derived from the per-project process checklist (`ptrack`); the same value drives the detail drawer, Table view, and Pipeline/PM Cards boards. Falls back to task counts when no checklist exists. Older projects can backfill the checklist on demand via "Generate from template".
- **Per-project records** — each project carries auxiliary records (`ptrack` process checklist, `survey`, `mom` meeting minutes, `bom` bill-of-materials, `verification`, `exceptions`) under `/api/projects/:id/records/:resource`.
- **Record export / import** — every record list supports Excel and PDF export (`frontend/src/utils/recordExport.js`, via `ExcelJS` / `jsPDF`) through the shared `ExportImportMenu` component; the project Table view additionally supports CSV export.
- **BOM Global view** (`/bom`) — a cross-project BOM inventory (`GET /api/bom/all`) with Excel import (maps rows to projects by name or id), Excel/PDF export, and an **INVENTORY toggle** that swaps the grid to the project-independent inventory catalogue (`/api/inventory`). Add New is inventory-first — only Device name is required; picking a project additionally creates a linked `bom_and_costing` copy. **Saved BOM lists** (`/api/bom-lists`) are named, reusable selections of inventory catalogue entries + a per-item quantity, scoped to a target project, FK-referenced not snapshotted.
- **Document uploads** — per-project PDF attachments (quotation / technical datasheet / result) under the detail drawer's "Documents" tab, with in-place preview, authenticated download, and owner-or-admin delete.
- **Dashboard view** (`/dashboard`) — a single-project executive report combining cost/procurement insights, document intelligence (survey, verification, MOM, exceptions), and the week-grouped process checklist, each exportable to Excel/PDF.
- **Summaries pipeline** (`/summaries`) — a 4-step calculator (Project → Inputs → Calculations → Results) over budget/team size/duration/complexity, producing a grade + ring gauges + charts per project, plus an all-projects comparison chart. Budget/team size/complexity edits are optimistic with a debounced `PATCH`; duration is what-if only and never persists. See [CLAUDE.md](CLAUDE.md#summaries-pipeline-summaries) for the full model.
- **Pipeline / PM Cards views** — read-only boards grouping projects by delivery stage (`/pipeline`) or by project manager (`/pm-cards`), with per-column risk indicators (overdue / critical counts).
- **Google Sheets sync** — `/api/sheets/export` and `/api/sheets/import` round-trip the project list with a configured spreadsheet.
- **Dark mode** — persisted in `localStorage`, respects OS preference on first visit.

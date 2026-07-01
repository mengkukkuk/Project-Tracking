# CLAUDE.md — Project-Tracking

Development guide for Claude Code. Read this before making changes.

## Dev Commands

```bash
# Backend (from backend/)
.venv/Scripts/python -m flask run --port 5000          # Windows dev server
.venv/Scripts/python -m pytest tests/ -v               # run all 25 tests
py -3.11 -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt

# Seed demo data (drops + recreates schema)
.venv/Scripts/python seed.py
# OR set SEED_ON_START=true in .env and restart Flask

# Frontend (from frontend/)
npm run dev        # Vite dev server → http://localhost:5173
npm run build      # production bundle → dist/
```

> **Note:** Use `.venv/Scripts/python` (Windows) to run pytest — the global Python env has a `hydra` package that breaks pytest plugin loading.

## Architecture

### Backend — `backend/`

| File | Purpose |
|---|---|
| `app/__init__.py` | App factory — wires DB, JWT, CORS, rate limiter, blueprints |
| `app/config.py` | All config from env vars; `Config` (prod) and `TestConfig` |
| `app/models.py` | SQLAlchemy ORM: `User`, `Project`, `Task`, `Comment`, `Activity`, `Tag`, `PTrack`, `PTemplate`, `ProcessTag`, record models (BOM, MOM, Survey, Verification, Exception) |
| `app/auth.py` | `/api/auth/*` — register, login, `/me`; rate-limited |
| `app/extensions.py` | Singletons: `jwt`, `limiter`, `Session` (scoped), `engine` |
| `app/validation.py` | Lightweight field validators — raises `ValidationError` (422) |
| `app/errors.py` | Centralized error handlers — all errors → `{"error": {...}}` |
| `app/api/helpers.py` | `log_activity()`, `require_owner_or_admin()` |
| `app/api/projects.py` | Project CRUD + `POST /<pid>/ptrack/generate` (backfill process checklist from template) |
| `app/api/tasks.py` | Task CRUD with owner-or-admin authz on delete |
| `app/api/comments.py` | Comment CRUD — delete requires author or admin |
| `app/api/records.py` | Per-project auxiliary records: `ptrack`, `survey`, `mom`, `bom`, `verification`, `exceptions`; also `GET /api/bom/all` (BOM rows across all projects, joined with project name) |
| `app/api/bom_lists.py` | `/api/bom-lists` CRUD — saved, named subsets of BOM rows (by FK reference, no snapshot), scoped to a target project; owner-or-admin gated on update/delete |
| `app/api/ptemplate.py` | Process checklist template (resolves process name via `process_tags` join) |
| `app/api/sheets.py` | Google Sheets export/import |
| `app/api/stats.py` | Dashboard aggregations via SQL `GROUP BY` (no Python loops) |
| `app/seed.py` | Demo data seeder — drops and recreates schema; dev only |

### Frontend — `frontend/src/`

| File | Purpose |
|---|---|
| `api/index.js` | Centralized fetch client — injects JWT, handles 401 redirect |
| `stores/auth.js` | Auth state: token, user, login/register/logout/restore |
| `stores/projects.js` | Project list, stats, filters, detail drawer, all CRUD actions |
| `stores/ui.js` | Toast notifications, dark mode toggle + persistence |
| `router.js` | Route guard — requires auth; restores session from token on boot |
| `views/OverviewView.vue` | KPI cards + charts (funnel, fiscal bars, domain donut, upcoming) |
| `views/PipelineView.vue` | Read-only Kanban-style board grouping projects by delivery stage (`/pipeline`); per-column value + overdue/critical risk counts |
| `views/PmCardsView.vue` | Read-only board grouping projects by PM (`/pm-cards`, `store.byPm`), incl. an "unassigned" column |
| `views/KanbanView.vue` | Drag-and-drop board with optimistic move + rollback |
| `views/TableView.vue` | Sortable, filterable, searchable project table; export via `ExportImportMenu` (Excel/PDF/CSV) |
| `views/BomGlobalView.vue` | Cross-project BOM inventory (`GET /api/bom/all`); Excel import (`parseBomInventoryExcel`) creates one `POST /api/projects/:id/records/bom` per matched row; Excel/PDF export; saved BOM lists via `BomListPicker` |
| `views/DashboardView.vue` | Single-project executive report: summary/health, cost & procurement, document intelligence (survey/verification/mom/exceptions), week-grouped process checklist; per-section + full-pack Excel/PDF export |
| `views/LoginView.vue` | Login + register form; demo button visible in dev mode only |
| `components/ProjectDetail.vue` | Slide-in drawer: detail, tasks checklist, process checklist, records, comments, activity |
| `components/ProjectForm.vue` | Create / edit modal |
| `components/ProcessChecklist.vue` | Grouped `ptrack` checkbox list; drives process-based progress; "Generate from template" empty state |
| `components/RecordList.vue` / `RecordForm.vue` | Generic CRUD table + modal for the auxiliary record resources |
| `components/ExportImportMenu.vue` | Shared export (Excel/PDF/CSV, configurable) + import trigger button cluster used by `RecordList`, `TableView`, `BomGlobalView`, `DashboardView` |
| `components/ImportResultModal.vue` | Import preview: valid/error/unmatched counts, per-row error table, confirm-to-commit |
| `components/BomListPicker.vue` | Modal to create/edit a saved BOM list — filterable checkbox table over the global BOM store, target-project picker |
| `utils/recordExport.js` | Excel export (ExcelJS, styled/frozen/auto-filter), PDF export (jsPDF + autoTable, Thai font), CSV export (projects only), and `parseBomInventoryExcel()` for BOM Global import |

## Key Decisions

### Typography (project default)
- **Single typeface: IBM Plex Sans Thai** — the only font used across the entire app.
- Defined once as the `--font` CSS variable in `frontend/src/assets/main.css` and loaded via Google Fonts there.
- **Always use `font-family: var(--font)`** (or `inherit`) in new components. Do NOT introduce additional font families (no serif display faces, no monospace).
- The `.mono` helper class is kept for figures/labels but now maps to `var(--font)` with `font-variant-numeric: tabular-nums` for column alignment — it is no longer a monospaced face.

### Authorization model
- **Admin**: full access to all resources
- **Member**: can only edit/delete their own projects and tasks; can delete own comments
- Enforced by `require_owner_or_admin(user, owner_id)` in `app/api/helpers.py`
- First user to register is automatically assigned `admin` role

### Rate limiting (Flask-Limiter)
- `POST /api/auth/login` — 10/min per IP
- `POST /api/auth/register` — 5/min per IP
- Storage: in-memory (dev); configure Redis (`RATELIMIT_STORAGE_URI`) for production

### Stats endpoint
- All aggregations use SQL `GROUP BY` + `func.count/sum/avg` — no full-table Python loops
- Upcoming projects fetched with `ORDER BY due_date LIMIT 8` in SQL

### Password policy
- Minimum 8 characters (enforced in `auth.py`)
- Hashed with Werkzeug PBKDF2

### JWT
- Access tokens only (no refresh), 12-hour expiry by default (`JWT_HOURS`)
- Identity: stringified `user.id`; role + name in additional claims
- Stored in `localStorage` (SPA trade-off)

### CORS
- Default: same-origin (`CORS_ORIGINS=""`)
- Dev: `CORS_ORIGINS=*` in `.env`
- Origin list is split and whitespace-stripped before passing to Flask-CORS

### Process-driven progress
- Every project's progress percentage is derived from its **process checklist** (`ptrack` rows): `processDone / processCount`.
- Falls back to the Task-entity counts (`taskDone / taskCount`) for projects with no process checklist.
- Backend ships `processCount` / `processDone` on **every** `Project.to_dict()` (list and detail), so the detail drawer bar, Table view Progress column, and Kanban cards stay consistent via the shared `taskProgress(p)` helper in `stores/projects.js`.
- Toggling a process checkbox is optimistic with rollback (mirrors `toggleTask`); `_syncProcessCounts()` swaps the `projects` array reference so @tanstack/vue-table re-runs the progress accessor without a manual refresh.
- Older projects (predating create-time seeding) get an empty state with a **Generate from template** button → `POST /api/projects/<pid>/ptrack/generate` (idempotent, owner/admin-gated).

### Database portability
- SQLAlchemy ORM — no DB-specific types; works on SQLite, PostgreSQL, MSSQL
- Schema auto-created on startup via `Base.metadata.create_all()`
- `pool_pre_ping=True` on all engines

### Record export / import
- Excel export uses `ExcelJS` (styled header, frozen pane, auto-filter, auto-fit columns, `dd/mm/yyyy` dates); PDF export uses `jsPDF` + `jspdf-autotable` with an embedded Thai font. Both are client-side only — no backend export endpoint.
- CSV export exists **only** for the project list (`TableView` → `exportProjectsCsv`); records use Excel/PDF only.
- BOM Global import (`parseBomInventoryExcel` in `utils/recordExport.js`) parses an `.xlsx`/`.xls` file, resolves each row's project by name or id, and returns `{valid, errors, unmatched}`. There is **no bulk-import endpoint** — `BomGlobalView.confirmImport()` issues one `POST /api/projects/<pid>/records/bom` per valid row.
- **BOM lists** (`/api/bom-lists`) store a reusable, named subset of BOM rows **by FK reference** (item ids + target project), not a snapshot — editing/deleting a referenced BOM row changes what the list shows.

## Testing

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -v
```

- 25 tests across auth, projects, tasks, comments, stats, and per-project records (ptrack/bom/mom + ptrack generate + process counts)
- Test DB: in-memory SQLite (`TestConfig`)
- Auth fixture password: `secret123` (meets 8-char minimum)
- Always run inside `.venv` to avoid global package conflicts

## Demo Credentials (seed data)

| Email | Password | Role |
|---|---|---|
| admin@scada.local | admin123 | admin |
| a@scada.local | password | member |
| b@scada.local | password | member |
| c@scada.local | password | member |

## Database

```bash
# PostgreSQL (current dev setup)
DATABASE_URL=postgresql+psycopg2://postgres:P%40ssw0rd@localhost:5432/ProjectTracking

# SQLite (zero config, default)
DATABASE_URL=sqlite:///project_tracking.db
```

To reseed: run `python seed.py` (drops + recreates all tables). Safe on dev DBs only.

## Common Pitfalls

- **pytest fails on global Python** — always use `.venv/Scripts/python -m pytest`
- **CORS errors in dev** — set `CORS_ORIGINS=*` in `backend/.env`
- **Rate limit 429 in manual testing** — login cap is 10/min per IP; wait or restart Flask
- **Tag names >48 chars** — `_resolve_tags()` raises 422 before the DB constraint fires
- **Owner check on seeded projects** — `owner_id` is assigned from the `pm` field (not admin); test authz with the actual owning user, not admin
- **`ptrack.checked` column name** — the ORM attribute is `checked` but maps the DB column literally named `"check"` (`Column("check", Boolean)`). Always access via the attribute, never raw SQL.
- **`ptemplate` has no `process` column** — the process *name* lives in `process_tags`, joined by `processid`. `_seed_ptrack` and `ptemplate` API resolve the name at read time.

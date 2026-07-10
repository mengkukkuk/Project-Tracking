# CLAUDE.md — Project-Tracking

Development guide for Claude Code. Read this before making changes.

## Dev Commands

```bash
# Backend (from backend/)
.venv/Scripts/python -m flask run --port 5000          # Windows dev server
.venv/Scripts/python -m pytest tests/ -v               # run all 73 tests
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
| `app/models.py` | SQLAlchemy ORM: `User`, `Project` (incl. nullable `team_size`/`complexity` used by the Summaries pipeline), `Task`, `Comment`, `Activity`, `Tag`, `PTrack`, `PTemplate`, `ProcessTag`, record models (BOM, MOM, Survey, Verification, Exception), `ProjectDocument` (uploaded PDF metadata) |
| `app/auth.py` | `/api/auth/*` — register, login, `/me`; rate-limited |
| `app/extensions.py` | Singletons: `jwt`, `limiter`, `Session` (scoped), `engine` |
| `app/validation.py` | Lightweight field validators — raises `ValidationError` (422) |
| `app/errors.py` | Centralized error handlers — all errors → `{"error": {...}}` |
| `app/permissions.py` | RBAC permission catalog — `ROLE_PERMISSIONS` (member ⊂ admin; super_admin = wildcard) + `role_has_permission()`. Plain data, no `models` import (avoids a cycle) |
| `app/api/helpers.py` | `log_activity()`, `require_owner_or_admin()` (scope gate), `require_permission()` (capability gate) |
| `app/api/users.py` | `GET /api/users` (directory for pickers) + `PATCH /api/users/:id/role` (role assignment, `roles.assign`-gated) |
| `app/api/projects.py` | Project CRUD + `POST /<pid>/ptrack/generate` (backfill process checklist from template) |
| `app/api/tasks.py` | Task CRUD with owner-or-admin authz on delete |
| `app/api/comments.py` | Comment CRUD — delete requires author or admin |
| `app/api/records.py` | Per-project auxiliary records: `ptrack`, `survey`, `mom`, `bom`, `verification`, `exceptions`; also `GET /api/bom/all` (BOM rows across all projects, joined with project name) |
| `app/api/bom_lists.py` | `/api/bom-lists` CRUD — saved, named subsets of BOM rows (by FK reference, no snapshot), scoped to a target project; owner-or-admin gated on update/delete |
| `app/api/documents.py` | Per-project PDF uploads (quotation/tds/result) — multipart upload, list, authenticated download, owner-or-admin delete; files under `DOCSTORE_DIR/<pid>/<type>/` with uuid names (see Document uploads below) |
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
| `views/TableView.vue` | Sortable, filterable, searchable project table; export via `ExportImportMenu` (Excel/PDF/CSV) |
| `views/BomGlobalView.vue` | Cross-project BOM inventory (`GET /api/bom/all`); Excel import (`parseBomInventoryExcel`) creates one `POST /api/projects/:id/records/bom` per matched row; Excel/PDF export; saved BOM lists via `BomListPicker` |
| `views/DashboardView.vue` | Single-project executive report: summary/health, cost & procurement, document intelligence (survey/verification/mom/exceptions), week-grouped process checklist; per-section + full-pack Excel/PDF export |
| `views/SummariesView.vue` | 4-step "Summaries" pipeline (`/summaries`): Project → editable Inputs (budget/team size/duration/complexity) → derived Calculations → Final Results (grade, ring gauges, charts) per project, plus an all-projects comparison chart. Math lives in `utils/summaryCalc.js` |
| `views/LoginView.vue` | Login + register form; demo button visible in dev mode only |
| `components/ProjectDetail.vue` | Slide-in drawer: detail, tasks checklist, process checklist, records, comments, activity |
| `components/ProjectForm.vue` | Create / edit modal |
| `components/ProcessChecklist.vue` | Grouped `ptrack` checkbox list; drives process-based progress; "Generate from template" empty state |
| `components/RecordList.vue` / `RecordForm.vue` | Generic CRUD table + modal for the auxiliary record resources |
| `components/ExportImportMenu.vue` | Shared export (Excel/PDF/CSV, configurable) + import trigger button cluster used by `RecordList`, `TableView`, `BomGlobalView`, `DashboardView` |
| `components/ImportResultModal.vue` | Import preview: valid/error/unmatched counts, per-row error table, confirm-to-commit |
| `components/BomListPicker.vue` | Modal to create/edit a saved BOM list — filterable checkbox table over the global BOM store, target-project picker |
| `components/ProjectDocuments.vue` | "Documents" drawer tab — three sections (Quotation/Technical Datasheet/Result) with multi-file PDF upload modal, in-place preview (`@embedpdf/vue-pdf-viewer`), blob download, delete |
| `components/summaries/*.vue` | `RingGauge`, `GradeChip`, `MetricRow` (presentational) and `ScoreBarChart`/`PerformanceRadar`/`ProjectsCompareChart` (vue-echarts, follow the `FunnelChart.vue` pattern) — used only by `SummariesView.vue` |
| `utils/recordExport.js` | Excel export (ExcelJS, styled/frozen/auto-filter), PDF export (jsPDF + autoTable, Thai font), CSV export (projects only), and `parseBomInventoryExcel()` for BOM Global import |
| `utils/summaryCalc.js` | Pure-JS math for the Summaries pipeline: input seeding (`seedTeamSize`/`seedComplexity`/`derivedDurationWeeks`), `computeMetrics`/`computeResults`/`gradeFor`. No store/API access, so the view can recompute on every keystroke |

## Key Decisions

### Typography (project default)
- **Single typeface: IBM Plex Sans Thai** — the only font used across the entire app.
- Defined once as the `--font` CSS variable in `frontend/src/assets/main.css` and loaded via Google Fonts there.
- **Always use `font-family: var(--font)`** (or `inherit`) in new components. Do NOT introduce additional font families (no serif display faces, no monospace).
- The `.mono` helper class is kept for figures/labels but now maps to `var(--font)` with `font-variant-numeric: tabular-nums` for column alignment — it is no longer a monospaced face.

### Authorization model
Three roles (`app/models.py:ROLES`, ordered most-privileged first): `super_admin`, `admin`, `member`.
- **super_admin**: system owner — wildcard permissions (`{"*"}`); the only role that can grant/modify the `super_admin` role.
- **admin**: org-scoped full access — all member capabilities plus `sheets.sync`, `templates.manage`, `roles.assign` (but **cannot** grant `super_admin`).
- **member**: own-record CRUD only (scope narrowed by ownership, not by missing capability).
- **First user to register is `admin`** (unchanged — register does not mint super_admin). A `super_admin` is reachable only via `seed.py` (`admin@scada.local` is seeded as super_admin), a direct DB edit, or promotion by an existing super_admin through the role endpoint. This is deliberate: with first-user-as-admin + "admin can't grant super_admin", there is no self-service path to the top role.

**Two orthogonal axes** — do not conflate them:
- **Capability** = "may this role do X at all?" → permission strings in `app/permissions.py` (`ROLE_PERMISSIONS`), checked via `User.has_permission(perm)` / `require_permission(user, perm)` in `app/api/helpers.py`. Resolved from the **live DB role at request time**, never from the JWT — so role changes take effect immediately.
- **Scope** = "own record vs any record?" → `require_owner_or_admin(user, owner_id)` (elevated roles = `admin`/`super_admin` via `ELEVATED_ROLES`, everyone else must own the row). This is why `member` still holds `projects.update` — the capability is granted, ownership narrows the scope.

The JWT still carries only `{role, name}`; `User.to_dict()` exposes a `permissions` list that is **advisory (UI-hiding only)** — the frontend uses `auth.hasPermission(perm)` to hide elements, but every backend guard re-derives from the live role.

**Role assignment**: `PATCH /api/users/:id/role` (`app/api/users.py`), gated `roles.assign`. Guards: only super_admin may grant/touch super_admin; you cannot change your own role. UI is a permission-gated `/users` view (`UsersView.vue`, shown in nav only when `hasPermission('roles.assign')`).

**Per-user page access (side-nav)**: `page.<key>` permission strings (`PAGE_KEYS` in `app/permissions.py` — `overview`/`pipeline`/`table`/`bom`/`dashboard`/`summaries`) gate each side-nav tab in the SPA (`meta.permission` in `router.js`, nav filtering in `App.vue`). Every role holds all `page.*` by default (they're unioned into `_MEMBER`); `User.page_access` (`models.py`, nullable `Text`, CSV of allowed keys) lets a `member`'s set be **narrowed** — `User.allowed_pages` / `has_permission()` intersect the stored keys against the live catalog, and `NULL`/empty means "all pages" so new catalog pages are auto-granted to unrestricted users. **Elevated roles (`admin`, `super_admin`) always get every page** — the override is members-only. `PATCH /api/users/:id/pages` (body `{pages: [...]}`), gated `pages.assign` (held by `admin` and `super_admin`), rejects elevated targets (403) and empty page lists (422 — a member must have somewhere to land); `set_user_role` clears `page_access` on promotion so a later demotion doesn't silently reapply a stale restriction. `/users` itself stays gated on `roles.assign`, not a `page.*` string. UI: a "Page access" checkbox column on `UsersView.vue`, editable when `hasPermission('pages.assign')`.

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
- Backend ships `processCount` / `processDone` on **every** `Project.to_dict()` (list and detail), so the detail drawer bar, Table view Progress column, and Pipeline/PM Cards views stay consistent via the shared `taskProgress(p)` helper in `stores/projects.js`.
- Toggling a process checkbox is optimistic with rollback (mirrors `toggleTask`); `_syncProcessCounts()` swaps the `projects` array reference so @tanstack/vue-table re-runs the progress accessor without a manual refresh.
- Older projects (predating create-time seeding) get an empty state with a **Generate from template** button → `POST /api/projects/<pid>/ptrack/generate` (idempotent, owner/admin-gated).
- **`status` is derived, not user-editable.** `Project.status` is computed server-side from live progress via `derived_status()` (`app/models.py`) across 5 buckets — `Pre-Sale` (0–19%) → `Project Initiation` (20–39%) → `award` (40–59%) → `Project Delivery` (60–79%) → `Completed` (80–100%). `PATCH /api/projects/:id` silently ignores any `status` key in the payload; the column is kept in sync via `recompute_project_status()` whenever progress-affecting fields change (ptrack toggle, task toggle, ptrack generate). There is no drag-and-drop status board — `PipelineView`/`PmCardsView` are read-only groupings by this derived status/PM.

### Summaries pipeline (`/summaries`)
- `Project.team_size` / `Project.complexity` are nullable ints (team_size ≥ 1, complexity 1–10), validated via `int_field` in `create_project`/`update_project` (`app/api/projects.py`); sending JSON `null` clears the field back to unset.
- When unset, the frontend seeds them at render time (never writes them back): `teamSize ← max(1, pms.length)`, `complexity ← priority map (low 3 / medium 5 / high 7 / critical 9)` — see `seedTeamSize`/`seedComplexity` in `utils/summaryCalc.js`.
- **Budget** maps to the existing `value` field (THB). **Duration (weeks)** is derived from `startDate`→`dueDate` and is a what-if-only input — editing it never persists, because rewriting `due_date` would trigger `recompute_ptrack_dates` and move overdue flags on other views.
- Editing Budget/Team Size/Complexity is optimistic with a 600ms debounced single `PATCH` (mirrors the checklist toggle's optimistic-with-rollback pattern) — no save button.

### Database portability
- SQLAlchemy ORM — no DB-specific types; works on SQLite, PostgreSQL, MSSQL
- Schema auto-created on startup via `Base.metadata.create_all()`
- `pool_pre_ping=True` on all engines

### Record export / import
- Excel export uses `ExcelJS` (styled header, frozen pane, auto-filter, auto-fit columns, `dd/mm/yyyy` dates); PDF export uses `jsPDF` + `jspdf-autotable` with an embedded Thai font. Both are client-side only — no backend export endpoint.
- CSV export exists **only** for the project list (`TableView` → `exportProjectsCsv`); records use Excel/PDF only.
- BOM Global import (`parseBomInventoryExcel` in `utils/recordExport.js`) parses an `.xlsx`/`.xls` file, resolves each row's project by name or id, and returns `{valid, errors, unmatched}`. There is **no bulk-import endpoint** — `BomGlobalView.confirmImport()` issues one `POST /api/projects/<pid>/records/bom` per valid row.
- **BOM lists** (`/api/bom-lists`) store a reusable, named subset of BOM rows **by FK reference** (item ids + target project), not a snapshot — editing/deleting a referenced BOM row changes what the list shows.

### Document uploads (docstore)
- Per-project PDF attachments, three types: `quotation` / `tds` (technical datasheet) / `result`. UI: "Documents" tab in the project detail drawer (`ProjectDocuments.vue`).
- **Files never keep the user's filename on disk.** Stored as `uuid4().hex + ".pdf"` under `DOCSTORE_DIR/<project_id>/<doc_type>/`; the original (possibly Thai) name lives in `project_documents.original_name` and is used as the download filename via `send_file(download_name=...)`. Do NOT introduce `secure_filename` here — it strips non-ASCII and would blank Thai names.
- Config: `DOCSTORE_DIR` (default `backend/docstore`, gitignored) and `MAX_UPLOAD_MB` (default 50 → Flask `MAX_CONTENT_LENGTH`; oversize → standard 413 envelope via `errors.py`). Tests point `DOCSTORE_DIR` at a per-test temp dir in `conftest.py`.
- Upload validates **all** files before writing any (`.pdf` extension + `%PDF-` magic bytes + non-empty) — a multi-file request is all-or-nothing. Authz mirrors records: any authenticated user may upload/list/download; delete is owner-or-admin. `documents.*` permission strings are UI-advisory only (like `records.*`).
- Deleting a document removes the disk file only after the DB commit (best-effort); deleting a project rmtree's its whole `docstore/<pid>/` folder after commit. Downloads go through `api.downloadDocument()` → blob → programmatic link, because a plain `<a href>` can't carry the JWT.
- **Preview** button (left of Download) opens the same authenticated blob in a modal via `@embedpdf/vue-pdf-viewer`'s `<PDFViewer :config="{ src: blobUrl, theme }" />` — the `src` prop accepts any URL string including `blob:`, so no server-side change or auth-header plumbing was needed for the viewer itself; the engine's `pdfium.wasm` ships bundled with the package (no CDN/self-hosting setup required). The viewer renders inside a `<embedpdf-container>` **web component with a shadow root** — DOM queries/tests against the preview must pierce `element.shadowRoot`, plain `document.querySelector` won't see inside it. `theme.preference` is wired to the app's dark-mode store (`ui.isDark`). Preview state (`previewDoc`/`previewUrl`/`closePreview`) is declared **before** the component's `watch(() => store.current?.id, ...)` block, since that watcher runs `{ immediate: true }` during setup and calls `closePreview()` — declaring the refs after it hits a temporal-dead-zone `ReferenceError` (a `function` declaration is hoisted, but the `const` refs it closes over are not initialized yet).
- The `project_documents` table is a NEW table, so `Base.metadata.create_all()` creates it automatically on restart — no ALTER migration needed (DDL also mirrored in `backend/init_db.sql`).

## Testing

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -v
```

- 73 tests across auth, projects (incl. `teamSize`/`complexity` create/PATCH/validation/null-clear), tasks, comments, stats, BOM lists, per-project records (ptrack/bom/mom + ptrack generate + process counts), documents (`test_documents.py` — upload/list/download/delete incl. Thai filenames, magic-byte validation, all-or-nothing multi-file, delete authz, project-delete disk cleanup, 413 cap), and RBAC (`test_rbac.py` — permission catalog, `/me` permissions, role-assignment endpoint authz incl. super_admin guardrails, refactored capability gates, per-user page access endpoint authz/validation/normalization/promotion-clearing)
- Test DB: in-memory SQLite (`TestConfig`)
- Auth fixture password: `secret123` (meets 8-char minimum)
- Always run inside `.venv` to avoid global package conflicts

## Demo Credentials (seed data)

| Email | Password | Role |
|---|---|---|
| admin@scada.local | admin123 | super_admin |
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

`Base.metadata.create_all()` does **not** add columns to an already-existing table — it only creates missing tables. Installs that predate `team_size`/`complexity` (added for the Summaries pipeline) need a one-time migration on their existing `projects` table:
```sql
ALTER TABLE projects ADD COLUMN IF NOT EXISTS team_size  INTEGER;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS complexity INTEGER;
```
On the PostgreSQL dev setup the table lives in the `pjtrk` schema (see `app/extensions.py:init_engine`, which sets `search_path=pjtrk`), so run it schema-qualified: `ALTER TABLE pjtrk.projects ADD COLUMN IF NOT EXISTS team_size INTEGER; ...`. `backend/init_db.sql` includes this migration inline. A fresh SQLite file or a fresh `python seed.py` run already has both columns — no action needed.

Same pattern for `users.page_access` (added for per-user page access, see Authorization model above): `ALTER TABLE pjtrk.users ADD COLUMN IF NOT EXISTS page_access TEXT;` on Postgres dev, or `ALTER TABLE users ADD COLUMN page_access TEXT;` on SQLite (no `IF NOT EXISTS` support for columns there). Also inlined in `backend/init_db.sql`.

## Common Pitfalls

- **pytest fails on global Python** — always use `.venv/Scripts/python -m pytest`
- **CORS errors in dev** — set `CORS_ORIGINS=*` in `backend/.env`
- **Rate limit 429 in manual testing** — login cap is 10/min per IP; wait or restart Flask
- **Tag names >48 chars** — `_resolve_tags()` raises 422 before the DB constraint fires
- **Owner check on seeded projects** — `owner_id` is assigned from the `pm` field (not admin); test authz with the actual owning user, not admin
- **`ptrack.checked` column name** — the ORM attribute is `checked` but maps the DB column literally named `"check"` (`Column("check", Boolean)`). Always access via the attribute, never raw SQL.
- **`ptemplate` has no `process` column** — the process *name* lives in `process_tags`, joined by `processid`. `_seed_ptrack` and `ptemplate` API resolve the name at read time.

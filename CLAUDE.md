# CLAUDE.md — Project-Tracking

Development guide for Claude Code. Read this before making changes.

## Dev Commands

```bash
# Backend (from backend/)
.venv/Scripts/python -m flask run --port 5000          # Windows dev server
.venv/Scripts/python -m pytest tests/ -v               # run all 16 tests
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
| `app/models.py` | SQLAlchemy ORM: `User`, `Project`, `Task`, `Comment`, `Activity`, `Tag` |
| `app/auth.py` | `/api/auth/*` — register, login, `/me`; rate-limited |
| `app/extensions.py` | Singletons: `jwt`, `limiter`, `Session` (scoped), `engine` |
| `app/validation.py` | Lightweight field validators — raises `ValidationError` (422) |
| `app/errors.py` | Centralized error handlers — all errors → `{"error": {...}}` |
| `app/api/helpers.py` | `log_activity()`, `require_owner_or_admin()` |
| `app/api/projects.py` | Project CRUD with owner-or-admin authz |
| `app/api/tasks.py` | Task CRUD with owner-or-admin authz on delete |
| `app/api/comments.py` | Comment CRUD — delete requires author or admin |
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
| `views/KanbanView.vue` | Drag-and-drop board with optimistic move + rollback |
| `views/TableView.vue` | Sortable, filterable, searchable project table |
| `views/LoginView.vue` | Login + register form; demo button visible in dev mode only |
| `components/ProjectDetail.vue` | Slide-in drawer: detail, tasks checklist, comments, activity |
| `components/ProjectForm.vue` | Create / edit modal |

## Key Decisions

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

### Database portability
- SQLAlchemy ORM — no DB-specific types; works on SQLite, PostgreSQL, MSSQL
- Schema auto-created on startup via `Base.metadata.create_all()`
- `pool_pre_ping=True` on all engines

## Testing

```bash
cd backend
.venv/Scripts/python -m pytest tests/ -v
```

- 16 tests across auth, projects, tasks, comments, stats
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

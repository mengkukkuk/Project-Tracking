# Project-Tracking

A full-stack project-tracking application for automation and engineering projects. Built with a **Vue 3 SPA** frontend and a **Flask REST API** backend, with JWT authentication, role-based authorization, CRUD operations, tasks, comments, an activity feed, rich analytics dashboards, and dark mode.

```
┌──────────────────────────────────────────────────────────────┐
│  Vue 3 SPA  (Vite · Pinia · vue-router · ECharts)           │
│   ├─ Auth        JWT login / register · route guard          │
│   ├─ Overview    KPIs · funnel · fiscal bars · domain donut  │
│   │              overdue / upcoming list                      │
│   ├─ Kanban      drag-and-drop status (optimistic + rollback) │
│   ├─ Table       sort · filter · search · pagination         │
│   └─ Detail      edit · tasks · comments · activity log      │
│        │  /api  (Vite proxy in dev)                          │
│        ▼                                                      │
│  Flask REST API  (app factory · blueprints · Flask-Limiter)  │
│   ├─ /api/auth        register · login · me        (JWT)     │
│   ├─ /api/projects    list / filter / search / CRUD          │
│   ├─ /api/projects/:id/tasks · /api/tasks/:id                │
│   ├─ /api/projects/:id/comments · /api/comments/:id          │
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

## Architecture Notes

- **Authorization** — admin can do anything; members can only modify their own projects/tasks. Enforced via `require_owner_or_admin()` in [`app/api/helpers.py`](backend/app/api/helpers.py).
- **Rate limiting** — login capped at 10 req/min, register at 5 req/min per IP (Flask-Limiter).
- **Stats** — all aggregations run as SQL `GROUP BY` queries; no full-table Python loops.
- **Kanban** — drag does an optimistic status update with automatic rollback on API failure.
- **Activity feed** — every create / update / status-move is logged per project.
- **Dark mode** — persisted in `localStorage`, respects OS preference on first visit.

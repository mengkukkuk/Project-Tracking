# SCADA MML — Project Tracker (Full‑Stack v2)

A modern project‑tracking application for SCADA / automation projects. Rewritten
from the original Google Apps Script dashboard into a **Vue 3 SPA** + **Flask
REST API**, with authentication, full CRUD, tasks, comments, an activity feed,
rich analytics, and a dark mode.

```
┌──────────────────────────────────────────────────────────────┐
│  Vue 3 SPA (Vite · Pinia · vue-router)                          │
│   ├─ Auth (JWT)  · login / register · route guard              │
│   ├─ Overview    · KPIs · funnel · fiscal bars · domain donut  │
│   │               · overdue / upcoming list                    │
│   ├─ Kanban      · drag-and-drop status (optimistic + rollback)│
│   ├─ Table       · sort · filter · search · CSV export         │
│   └─ Detail drawer · edit · tasks · comments · activity log    │
│        │  /api  (Vite proxy in dev)                            │
│        ▼                                                       │
│  Flask REST API (app factory · blueprints)                     │
│   ├─ /api/auth      register · login · me        (JWT)         │
│   ├─ /api/projects  list (filter/search/sort/paginate) · CRUD  │
│   ├─ /api/projects/:id/tasks · /api/tasks/:id                  │
│   ├─ /api/projects/:id/comments · /api/comments/:id            │
│   ├─ /api/stats     server-side aggregation                    │
│   └─ /api/users · /api/health                                  │
│        ▼                                                       │
│  SQLAlchemy → SQLite (dev) | PostgreSQL | MSSQL                │
└──────────────────────────────────────────────────────────────┘
```

## What changed from v1

| Area | v1 | v2 |
|------|----|----|
| Auth | none | JWT login/register, route guard, role-based comment deletion |
| CRUD UI | API only, **no forms** | create/edit/delete modals + inline detail drawer |
| Data model | flat project row | + users, tasks, comments, activity feed, tags, priority, dates |
| Validation | none (`int()` could crash) | typed validators → consistent `422` errors |
| Backend | single file, `debug=True`, CORS `*` | app factory, blueprints, env config, error handlers |
| Server features | — | filtering, search, sorting, pagination, richer stats |
| Charts | `var(--css)` colours broke in canvas | theme-aware palette, reacts to dark mode |
| Dark mode | reset on reload | persisted (localStorage) + respects OS preference |
| UX | bare loading text | toasts, loading/empty states, due-date warnings |
| Tests | none | 16 pytest cases (auth, projects, tasks, comments, stats) |

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # optional
pip install -r requirements.txt                     # add psycopg2-binary / pyodbc for prod DBs

cp .env.example .env        # optional — defaults work out of the box (SQLite)
python seed.py              # create schema + demo data (admin@scada.local / admin123)
python wsgi.py              # http://localhost:5000
```

Choose a database purely via `DATABASE_URL` — no code changes:

```bash
export DATABASE_URL="postgresql+psycopg2://user:pass@localhost:5432/scada_mml"
export DATABASE_URL="mssql+pyodbc://user:pass@host/scada_mml?driver=ODBC+Driver+18+for+SQL+Server"
```

Run the tests:

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

## Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies /api → :5000)
```

Open http://localhost:5173 and sign in with **admin@scada.local / admin123**
(the first account to register becomes the admin).

## Production

- **Frontend:** `npm run build` → serve `dist/` via Nginx/IIS. Set
  `VITE_API_BASE` if the API is not co-located.
- **Backend:** `waitress-serve --port=5000 wsgi:app` (Windows) or
  `gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app` (Linux). Set a strong `SECRET_KEY`
  and a comma-separated `CORS_ORIGINS` allow-list.

## Notes

- The Pinia store fetches once; KPIs, funnel, fiscal bars and Kanban columns are
  all derived projections, so they stay in sync automatically.
- Kanban drag does an **optimistic** update with rollback on API failure.
- Every create/update/move is recorded in the per-project **activity feed**.

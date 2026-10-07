# Process templates (`template_no`) — design

**Date:** 2026-10-07 · **Status:** implemented

## Goal

A *template* is the set of `process_tags` + `ptemplate` rows that share a `template_no`. Today the code ignores `template_no`: every new project is seeded from **all** `ptemplate` rows and the date chain reads **all** `process_tags` by process name. This work makes templates first-class:

1. Authorized users (`templates.manage`: admin, super_admin) create and edit templates on a new `/templates` page.
2. Creating a project lets the user pick a template; that template alone seeds the project's `ptrack` checklist.
3. The picked template drives that project's due-date chain and day ranges; other templates never leak in.

## Findings (live DB, 2026-10-07)

- `ptemplate(id, task, processid, results, undertaker, template_no)` and `process_tags(id, processid, process, day_range, template_no)` already exist in `pjtrk`; one template (`template_no=1`, 5 processes, 19 tasks). All columns nullable, no FKs. `results`/`undertaker` were unknown to `models.py`.
- `projects` has **no** `template_no`; nothing records which template a project uses.
- `processid` restarts at 1 per template, so the key is `(template_no, processid)`.
- The frontend never called `/api/ptemplate`.

## Design

### Data
- **New column** `projects.template_no INTEGER NULL` (NULL ≡ template 1). The user applies the `ALTER` by hand (see Rollout); also mirrored in `init_db.sql`.
- `PTemplate` gains `template_no`, `results`, `undertaker`; `ProcessTag` gains `template_no`. ORM `default=1` on both so legacy inserts (tests, seed) land in template 1; reads use `coalesce(template_no, 1)` so NULL rows count as template 1.
- Template existence is **derived** (no `templates` table): a template exists iff it has ≥1 `process_tags` row. Therefore a new template is created with a starter process, and the last process of a template cannot be deleted (409).
- Templates have no name — they are labelled "Template N".

### Backend
- `app/api/helpers.py`: `project_template_no(project)` (`or 1`), `template_exists(no)`.
- `create_project` accepts `templateNo` (int ≥ 1, default 1), 422 if an *explicitly sent* template doesn't exist (omitted keeps the old behaviour, so projects can still be created before any template exists), stores it. `PATCH` silently ignores `templateNo` (immutable after creation, like `status`).
- `_seed_ptrack`, `recompute_ptrack_dates`, and the `dayRange`/`cumulativeDays` enrichment in `records.py` read only the project's own template. `ptrack/generate` uses the project's saved template.
- `Project.to_dict()` exposes `templateNo` (`template_no or 1`).
- In `app/api/ptemplate.py` (same blueprint, under `/api`):
  - `GET /templates` → `{items:[{templateNo, processCount, taskCount, projectCount}]}` (any authed user — feeds the picker).
  - `GET /templates/<no>` → `{templateNo, processes:[{id, processId, process, dayRange, tasks:[{id, task, results, undertaker}]}]}`, 404 if missing.
  - `POST /templates` `{cloneFrom?}` → next `template_no` (max+1); clones that template's rows, or creates one starter process (`"New process"`, 1 day). `templates.manage`.
  - `POST /templates/<no>/processes` `{process, dayRange}` → `processid = max+1` within the template.
  - `PATCH /process-tags/<id>` `{process?, dayRange?}`; `DELETE /process-tags/<id>` (also deletes that process's `ptemplate` rows; 409 if it is the template's last process).
- `/ptemplate`: `POST` takes `templateNo` (default 1), `results`, `undertaker` and requires the `(templateNo, processId)` process to exist (422); new `PATCH /ptemplate/<id>`; `DELETE` unchanged. All `templates.manage`.
- Editing a template never touches existing projects' `ptrack` (snapshot semantics, as today).

### Frontend
- `api/index.js`: template/process/task methods.
- `ProjectForm.vue` (create mode only): "Process template" select (default 1, shows process/task counts); sends `templateNo`.
- `views/TemplatesView.vue` at `/templates`, `meta.permission: 'templates.manage'`, nav entry beside Users (not a `page.*` key). Left: template list + "New template" (blank or clone current). Right: processes (rename, day range, add, delete) each with its tasks (edit task / results / undertaker, add, delete). Uses `var(--font)` and existing form/button classes; `RouteSkeleton` `generic` while loading.
- `ProjectDetail.vue`: read-only "Template N" chip in the hero.

### Out of scope
Changing a project's template after creation; deleting a whole template; drag-reordering; naming templates; carrying `results`/`undertaker` into `ptrack`.

## Testing
pytest (`test_templates.py`): seed only the chosen template; default = 1; 422 unknown template; date chain/dayRange isolated per template; `PATCH` ignores `templateNo`; member 403 on every write, member can read; clone; last-process 409; process delete cascades tasks. Existing suites must stay green. UI verified in the browser pane against a throwaway SQLite backend.

## Rollout
Run once on the live DB (then restart Flask — no auto-reload):
```sql
ALTER TABLE pjtrk.projects ADD COLUMN IF NOT EXISTS template_no INTEGER;
```
Existing projects keep `NULL` ≡ template 1, which is correct because only template 1 exists.

## Addendum (2026-10-07, follow-up)
- **Names:** new `template_names(template_no PK, name)` table (auto-created by `create_all()`); `name` returned by `GET /templates[/<no>]`, set via `POST /templates {name}` / `PATCH /templates/<no> {name}` (blank clears).
- **Save button:** `/templates` stages every edit in a draft; **Save** applies adds → updates → deletes. Discard/leave/switch prompt when dirty.
- **Change template later** (previously out of scope): `POST /projects/<pid>/template {templateNo}` replaces the project's `ptrack` with the new template's rows, carrying `checked`/`reference` over for tasks with identical text; owner-or-admin; no-op for the current template; activity logged. UI: switcher on the project's Process tab with a confirm dialog.

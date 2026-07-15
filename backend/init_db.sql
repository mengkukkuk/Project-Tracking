-- =============================================================
-- Project Tracking — PostgreSQL initialization script
-- Usage:
--   1. Create the database first:
--        createdb -U postgres projecttracking
--      (or CREATE DATABASE projecttracking; in psql)
--   2. Run this script:
--        psql -U postgres -d projecttracking -f init_db.sql
--
-- The script creates the `pjtrk` schema and sets search_path automatically.
-- The schema name MUST stay in sync with `app/extensions.py:init_engine`
-- (which sets `options=-csearch_path=pjtrk` on every PostgreSQL connection).
--
-- This mirrors the tables/columns actually present on the dev database
-- (DB_NAME=projecttracking, schema=pjtrk), which is normally bootstrapped by
-- SQLAlchemy's `Base.metadata.create_all()` (see `app/models.py`) rather than
-- by this file. Enum-style constraints (project status/priority, user role,
-- activity action) and the `progress` 0-100 range are enforced by the app
-- layer (`app/validation.py`), not by DB CHECK constraints — this script
-- intentionally does not add them so a fresh run matches what the ORM
-- creates. Likewise, `updated_at` bumping is done by SQLAlchemy
-- (`onupdate=func.now()`), not a DB trigger.
--
-- This script is OPTIONAL: `python seed.py` will bootstrap the schema and
-- tables automatically on a fresh DB. Use this script when you want the
-- schema without the demo data (e.g. for production initialization).
--
-- Idempotent: safe to re-run (IF NOT EXISTS / ON CONFLICT DO NOTHING).
-- Drop order honors FK dependencies (see bottom of the file).
-- =============================================================

-- ── Schema ────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS pjtrk;
SET search_path TO pjtrk;

-- ── Extensions ────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), pgcrypt helpers

-- =============================================================
-- TABLES
-- =============================================================

-- ── users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL        PRIMARY KEY,
  name          VARCHAR(128)  NOT NULL,
  email         VARCHAR(255)  NOT NULL,
  password_hash VARCHAR(255)  NOT NULL,
  role          VARCHAR(16)   NOT NULL,       -- 'admin' | 'member' (app-enforced)
  page_access   TEXT,
  created_at    TIMESTAMP,
  user_id       SERIAL        NOT NULL        -- internal employee / staff ID (not ORM-mapped; set via raw SQL, see seed.py)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Existing installs predating per-user page access: CREATE TABLE IF NOT EXISTS
-- above is a no-op once the table exists, so add the column explicitly.
-- CSV of allowed page keys (see backend/app/permissions.py PAGE_KEYS);
-- NULL = default (all pages).
ALTER TABLE users ADD COLUMN IF NOT EXISTS page_access TEXT;

-- ── tags ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
  id    SERIAL       PRIMARY KEY,
  name  VARCHAR(48)  NOT NULL,
  color VARCHAR(16)
);

CREATE UNIQUE INDEX IF NOT EXISTS tags_name_key ON tags (name);

-- ── projects ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
  id          SERIAL          PRIMARY KEY,
  name        VARCHAR(255)    NOT NULL,
  description TEXT,
  domain      VARCHAR(64),                   -- Vision Sensor, Robot, PLC, IoT, AI
  customer    VARCHAR(255),
  pm          VARCHAR(128),                  -- project manager (free text)
  status      VARCHAR(64)     NOT NULL,      -- pipeline stage (app-enforced, see STAGES)
  priority    VARCHAR(16)     NOT NULL,      -- 'low' | 'medium' | 'high' | 'critical' (app-enforced)
  value       NUMERIC(14, 2),                -- THB
  progress    INTEGER,                       -- 0-100 (app-enforced)
  fiscal_year VARCHAR(8),                    -- '69', '70', '71', 'future'
  start_date  DATE,
  due_date    DATE,
  owner_id    INTEGER         REFERENCES users (id) ON DELETE SET NULL,
  created_at  TIMESTAMP,
  updated_at  TIMESTAMP,
  team_size   INTEGER,
  complexity  INTEGER
);

-- Existing installs predating team_size/complexity: CREATE TABLE IF NOT EXISTS
-- above is a no-op once the table exists, so add the columns explicitly.
ALTER TABLE projects ADD COLUMN IF NOT EXISTS team_size  INTEGER;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS complexity INTEGER;

-- ── project_tags (M2M join table) ─────────────────────────────
CREATE TABLE IF NOT EXISTS project_tags (
  project_id  INTEGER  NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  tag_id      INTEGER  NOT NULL REFERENCES tags     (id) ON DELETE CASCADE,
  PRIMARY KEY (project_id, tag_id)
);

-- ── project_pms (M2M: project managers per project) ───────────
CREATE TABLE IF NOT EXISTS project_pms (
  project_id  INTEGER  NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER  NOT NULL REFERENCES users    (id) ON DELETE CASCADE,
  PRIMARY KEY (project_id, user_id)
);

-- ── tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
  id          SERIAL        PRIMARY KEY,
  project_id  INTEGER       NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  title       VARCHAR(255)  NOT NULL,
  done        BOOLEAN,
  assignee    VARCHAR(128),
  due_date    DATE,
  created_at  TIMESTAMP
);

-- ── comments ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comments (
  id          SERIAL    PRIMARY KEY,
  project_id  INTEGER   NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER            REFERENCES users    (id) ON DELETE SET NULL,
  body        TEXT      NOT NULL,
  created_at  TIMESTAMP
);

-- ── activities (audit log) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS activities (
  id          SERIAL       PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  action      VARCHAR(64)  NOT NULL,   -- 'created' | 'updated' | 'moved' | 'task' (app-enforced)
  detail      VARCHAR(512),
  created_at  TIMESTAMP
);

-- ── ptemplate (process / task template) ───────────────────────
CREATE TABLE IF NOT EXISTS ptemplate (
  id         SERIAL  PRIMARY KEY,
  task       TEXT,
  processid  INTEGER,
  results    TEXT,
  undertaker TEXT
);

-- ── process_tags ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS process_tags (
    id          SERIAL  PRIMARY KEY,
    processid   INTEGER,
    process     TEXT,
    day_range   INTEGER
);

-- ── ptrack (per-project process tracking) ─────────────────────
CREATE TABLE IF NOT EXISTS ptrack (
    id          SERIAL   PRIMARY KEY,
    project_id  INTEGER  NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    user_id     INTEGER  REFERENCES users    (id) ON DELETE SET NULL,
    process     TEXT,
    pm          TEXT,
    start_date  DATE     DEFAULT NOW(),
    due_date    DATE     DEFAULT NOW(),
    task        TEXT,
    status      TEXT,
    "check"     BOOLEAN  DEFAULT FALSE,
    reference   TEXT
);

CREATE INDEX IF NOT EXISTS ix_ptrack_project_id ON ptrack (project_id);

-- ── survey_report ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS survey_report (
  id           SERIAL       PRIMARY KEY,
  project_id  INTEGER       NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER                REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE,
  department   TEXT,
  requirement  TEXT,
  issue        TEXT,
  limitation   TEXT,
  result       TEXT,
  conclude     TEXT,
  surveyor     TEXT
);

-- ── customer_mom (meeting minutes) ────────────────────────────
CREATE TABLE IF NOT EXISTS customer_mom (
  id           SERIAL  PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE,
  participant  TEXT,
  topic        TEXT,
  concerns     TEXT,
  conclude     TEXT,
  todo         TEXT
);

-- ── bom_and_costing (bill of materials & costing) ─────────────
CREATE TABLE IF NOT EXISTS bom_and_costing (
  id            SERIAL      PRIMARY KEY,
  project_id    INTEGER     NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  date_approve  DATE,
  category      TEXT,                    -- legacy free text; kept as display fallback
  category_id   INTEGER,                 -- -> lookup_type.lookup_type_id (FK enforced by ORM)
  type_id       INTEGER,                 -- -> lookup_value.lookup_value_id (FK enforced by ORM)
  device_name   TEXT,
  version       TEXT,
  spec          TEXT,
  quantity      INTEGER,
  unit          TEXT,
  "position"    TEXT,
  unit_price    INTEGER,
  total_price   INTEGER,
  lead_time     INTEGER,
  supplier      TEXT
);

-- Existing installs predating the Category/Type taxonomy references: CREATE
-- TABLE IF NOT EXISTS above is a no-op once the table exists, so add the columns
-- explicitly (plain INTEGER; the lookup_* tables are defined lower in this file,
-- so an inline FK here would forward-reference — the FK is ORM-enforced).
ALTER TABLE bom_and_costing ADD COLUMN IF NOT EXISTS category_id INTEGER;
ALTER TABLE bom_and_costing ADD COLUMN IF NOT EXISTS type_id     INTEGER;

-- ── internal_verification ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS internal_verification (
  id           SERIAL   PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE,
  approver     TEXT,
  test_system  TEXT,
  test_result  TEXT,
  defected     TEXT,
  solution     TEXT,
  status       BOOLEAN
);

-- ── exception_log ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exception_log (
  id            SERIAL  PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date          DATE,
  informer      TEXT,
  order_list    TEXT,
  effect_price  TEXT,
  effect_tech   TEXT,
  date_new_bom  DATE,
  date_new_pps  DATE
);

-- ── inventory (reusable device catalogue / price book) ────────
-- Project-independent by design: no project_id, no position, no quantity.
-- A catalogue entry is the device; how many a given list wants lives on
-- bom_list_items.quantity. Saved BOM lists draw from this table.
CREATE TABLE IF NOT EXISTS inventory (
  id            SERIAL      PRIMARY KEY,
  category_id   INTEGER,                 -- -> lookup_type.lookup_type_id (FK enforced by ORM)
  type_id       INTEGER,                 -- -> lookup_value.lookup_value_id (FK enforced by ORM)
  device_name   TEXT,
  version       TEXT,
  spec          TEXT,
  unit          TEXT,
  unit_price    INTEGER,
  supplier      TEXT,
  lead_time     INTEGER,
  created_at    TIMESTAMP,
  updated_at    TIMESTAMP
);

-- ── bom_lists (saved, named selections of catalogue entries) ──
CREATE TABLE IF NOT EXISTS bom_lists (
  id          SERIAL   PRIMARY KEY,
  name        TEXT     NOT NULL,
  project_id  INTEGER  NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  owner_id    INTEGER           REFERENCES users    (id) ON DELETE SET NULL,
  created_at  TIMESTAMP,
  updated_at  TIMESTAMP
);

-- ── bom_list_items (M2M: bom_lists <-> inventory, + quantity) ─
-- quantity belongs here, not on inventory: it is a property of THIS list's
-- use of the catalogue entry, not of the device itself.
CREATE TABLE IF NOT EXISTS bom_list_items (
  list_id       INTEGER  NOT NULL REFERENCES bom_lists (id) ON DELETE CASCADE,
  inventory_id  INTEGER  NOT NULL REFERENCES inventory (id) ON DELETE CASCADE,
  quantity      INTEGER,
  PRIMARY KEY (list_id, inventory_id)
);

-- ── project_documents (uploaded PDFs: quotation / tds / result) ─
-- Disk files live at <DOCSTORE_DIR>/<project_id>/<doc_type>/<stored_name>;
-- stored_name is server-generated (uuid + '.pdf'), original_name keeps the
-- user's (possibly Thai) filename for display/download.
CREATE TABLE IF NOT EXISTS project_documents (
  id             SERIAL        PRIMARY KEY,
  project_id     INTEGER       NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id        INTEGER                REFERENCES users    (id) ON DELETE SET NULL,
  doc_type       VARCHAR(16)   NOT NULL,   -- 'quotation' | 'tds' | 'result' (app-enforced)
  original_name  VARCHAR(255)  NOT NULL,
  stored_name    VARCHAR(64)   NOT NULL,
  size_bytes     INTEGER       NOT NULL,
  created_at     TIMESTAMP
);

CREATE TABLE lookup_type (
     lookup_type_id SERIAL        PRIMARY KEY,
     code text UNIQUE NOT NULL,
     name text NOT NULL,
     description text,
     is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE lookup_value (
      lookup_value_id SERIAL        PRIMARY KEY,
      lookup_type_id INT NOT NULL,
      code text NOT NULL,
      display_name text NOT NULL,
      sort_order INT DEFAULT 0,
      is_default BOOLEAN DEFAULT false,
      is_active BOOLEAN DEFAULT true,

      FOREIGN KEY (lookup_type_id)
          REFERENCES lookup_type(lookup_type_id)
);

-- =============================================================
-- TEARDOWN (uncomment to drop everything and start fresh)
-- =============================================================
-- SET search_path TO pjtrk;
-- DROP TABLE IF EXISTS project_documents     CASCADE;
-- DROP TABLE IF EXISTS bom_list_items        CASCADE;
-- DROP TABLE IF EXISTS bom_lists             CASCADE;
-- DROP TABLE IF EXISTS inventory             CASCADE;
-- DROP TABLE IF EXISTS exception_log         CASCADE;
-- DROP TABLE IF EXISTS internal_verification CASCADE;
-- DROP TABLE IF EXISTS bom_and_costing       CASCADE;
-- DROP TABLE IF EXISTS customer_mom          CASCADE;
-- DROP TABLE IF EXISTS survey_report         CASCADE;
-- DROP TABLE IF EXISTS ptrack                CASCADE;
-- DROP TABLE IF EXISTS process_tags          CASCADE;
-- DROP TABLE IF EXISTS ptemplate             CASCADE;
-- DROP TABLE IF EXISTS activities            CASCADE;
-- DROP TABLE IF EXISTS comments              CASCADE;
-- DROP TABLE IF EXISTS tasks                 CASCADE;
-- DROP TABLE IF EXISTS project_pms           CASCADE;
-- DROP TABLE IF EXISTS project_tags          CASCADE;
-- DROP TABLE IF EXISTS projects              CASCADE;
-- DROP TABLE IF EXISTS tags                  CASCADE;
-- DROP TABLE IF EXISTS users                 CASCADE;
-- -- Optional: drop the entire schema (also removes anything not listed above)
-- -- DROP SCHEMA IF EXISTS pjtrk CASCADE;

-- =============================================================
-- Project Tracking — PostgreSQL initialization script
-- Usage:
--   1. Create the database first:
--        createdb -U postgres ProjectTracking
--      (or  CREATE DATABASE "ProjectTracking";  in psql)
--   2. Run this script:
--        psql -U postgres -d ProjectTracking -f init_db.sql
--
-- The script creates the `pjtrk` schema and sets search_path automatically.
-- The schema name MUST stay in sync with `app/extensions.py:init_engine`
-- (which sets `options=-csearch_path=pjtrk` on every PostgreSQL connection).
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

-- ── Trigger function: auto-update updated_at ──────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- =============================================================
-- TABLES
-- =============================================================

-- ── users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            SERIAL        PRIMARY KEY,
  name          VARCHAR(128)  NOT NULL,
  email         VARCHAR(255)  NOT NULL,
  password_hash VARCHAR(255)  NOT NULL,
  role          VARCHAR(16)   NOT NULL DEFAULT 'member'
                              CHECK (role IN ('admin', 'member')),
  created_at    TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email);
CREATE        INDEX IF NOT EXISTS ix_users_email ON users (email);

-- ── tags ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tags (
  id    SERIAL       PRIMARY KEY,
  name  VARCHAR(48)  NOT NULL,
  color VARCHAR(16)  NOT NULL DEFAULT '#64748b'
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_name ON tags (name);

-- ── projects ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
  id          SERIAL          PRIMARY KEY,
  name        VARCHAR(255)    NOT NULL,
  description TEXT,
  domain      VARCHAR(64),                   -- Vision Sensor, Robot, PLC, IoT, AI
  customer    VARCHAR(255),
  pm          VARCHAR(128),                  -- project manager (free text)
  status      VARCHAR(64)     NOT NULL DEFAULT 'Pre-Sale'
              CHECK (status IN (
                'Pre-Sale', 'Project Initiation', 'Award',
                'Project Delivery', 'Completed'
              )),
  priority    VARCHAR(16)     NOT NULL DEFAULT 'medium'
              CHECK (priority IN ('low', 'medium', 'high', 'critical')),
  value       NUMERIC(14, 2)  NOT NULL DEFAULT 0,   -- THB
  progress    INTEGER         NOT NULL DEFAULT 0
              CHECK (progress BETWEEN 0 AND 100),
  fiscal_year VARCHAR(8),                    -- '69', '70', '71', 'future'
  start_date  DATE,
  due_date    DATE,
  owner_id    INTEGER         REFERENCES users (id) ON DELETE SET NULL,
  created_at  TIMESTAMP       NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_projects_status     ON projects (status);
CREATE INDEX IF NOT EXISTS ix_projects_priority   ON projects (priority);
CREATE INDEX IF NOT EXISTS ix_projects_owner_id   ON projects (owner_id);
CREATE INDEX IF NOT EXISTS ix_projects_due_date   ON projects (due_date);
CREATE INDEX IF NOT EXISTS ix_projects_updated_at ON projects (updated_at DESC);

-- Auto-bump updated_at on every UPDATE
DROP TRIGGER IF EXISTS trg_projects_updated_at ON projects;
CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

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
  done        BOOLEAN       NOT NULL DEFAULT FALSE,
  assignee    VARCHAR(128),
  due_date    DATE,
  created_at  TIMESTAMP     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_tasks_project_id ON tasks (project_id);

-- ── comments ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comments (
  id          SERIAL    PRIMARY KEY,
  project_id  INTEGER   NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER            REFERENCES users    (id) ON DELETE SET NULL,
  body        TEXT      NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_comments_project_id ON comments (project_id);

-- ── activities (audit log) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS activities (
  id          SERIAL       PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  action      VARCHAR(64)  NOT NULL
              CHECK (action IN ('created', 'updated', 'moved', 'task')),
  detail      VARCHAR(512),
  created_at  TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_activities_project_id ON activities (project_id);
CREATE INDEX IF NOT EXISTS ix_activities_created_at ON activities (created_at DESC);

-- ── ptemplate (process / task template) ───────────────────────
CREATE TABLE IF NOT EXISTS ptemplate (
  id         SERIAL  PRIMARY KEY,
  task       TEXT,
  processid  INTEGER
);

CREATE TABLE IF NOT EXISTS process_tags (
    id         SERIAL  PRIMARY KEY,
    processid integer,
    process   text,
    day_range  INTEGER
);

-- ── ptrack (per-project process tracking) ─────────────────────
CREATE TABLE IF NOT EXISTS ptrack (
  id          SERIAL   PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
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
  id           SERIAL  PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE    DEFAULT NOW(),
  department   TEXT,
  requirement  TEXT,
  issue        TEXT,
  limitation   TEXT,
  result       TEXT,
  conclude     TEXT
);

-- ── customer_mom (meeting minutes) ────────────────────────────
CREATE TABLE IF NOT EXISTS customer_mom (
  id           SERIAL  PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE    DEFAULT NOW(),
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
  date_approve  DATE        DEFAULT NOW(),
  category      TEXT,
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

-- ── internal_verification ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS internal_verification (
  id           SERIAL   PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date         DATE     DEFAULT NOW(),
  approver     TEXT,
  test_system  TEXT,
  test_result  TEXT,
  defected     TEXT,
  solution     TEXT,
  status       BOOLEAN  DEFAULT TRUE
);

-- ── exception_log ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exception_log (
  id            SERIAL  PRIMARY KEY,
  project_id  INTEGER      NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
  user_id     INTEGER               REFERENCES users    (id) ON DELETE SET NULL,
  date          DATE    DEFAULT NOW(),
  informer      TEXT,
  order_list    TEXT,
  effect_price  TEXT,
  effect_tech   TEXT,
  date_new_bom  DATE,
  date_new_pps  DATE
);

-- =============================================================
-- SEED: default tags (matches seed.py — idempotent)
-- =============================================================
INSERT INTO tags (name, color) VALUES
  ('กรมสรรพสามิต', '#3b82f6'),   -- excise dept  (blue)
  ('เอกชน',        '#10b981'),   -- private      (green)
  ('เร่งด่วน',    '#ef4444'),   -- urgent       (red)
  ('R&D',          '#8b5cf6')    -- R&D          (purple)
ON CONFLICT (name) DO NOTHING;

-- =============================================================
-- TEARDOWN (uncomment to drop everything and start fresh)
-- =============================================================
-- SET search_path TO pjtrk;
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
-- DROP TABLE IF EXISTS project_tags          CASCADE;
-- DROP TABLE IF EXISTS projects              CASCADE;
-- DROP TABLE IF EXISTS tags                  CASCADE;
-- DROP TABLE IF EXISTS users                 CASCADE;
-- DROP FUNCTION IF EXISTS set_updated_at();
-- -- Optional: drop the entire schema (also removes anything not listed above)
-- -- DROP SCHEMA IF EXISTS pjtrk CASCADE;

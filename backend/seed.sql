
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
-- SEED: process_tags — canonical process order with day budgets
-- =============================================================
INSERT INTO process_tags (processid, process, day_range) VALUES
     (1, 'Site Survey & Draft',  13)
ON CONFLICT DO NOTHING;

-- =============================================================
-- SEED: ptemplate — 20 default process checklist tasks
-- =============================================================
INSERT INTO ptemplate (task, processid) VALUES
        ('รับโจทย์ / เข้าสำรวจหน้างาน / บันทึกความต้องการลูกค้า (Requirement)', 1);


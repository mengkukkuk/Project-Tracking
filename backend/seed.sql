
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
     (1, 'Site Survey & Draft',  13),
     (2, 'Verify Solution',       6),
     (3, 'Presentation',          6),
     (4, 'BOM List & Costing',    6),
     (5, 'Executive Review',      6),
     (6, 'Post-Submission',      13)
ON CONFLICT DO NOTHING;

-- =============================================================
-- SEED: ptemplate — 20 default process checklist tasks
-- =============================================================
INSERT INTO ptemplate (task, processid) VALUES
        ('รับโจทย์ / เข้าสำรวจหน้างาน / บันทึกความต้องการลูกค้า (Requirement)', 1),
        ('วิเคราะห์ปัญหาหลัก (Pain Point)', 1),
        ('อัปเดตข้อมูลให้ทีมภายในทราบ ภายใน 1-3 วันแรก', 1),
        ('ทำร่างโซลูชัน (Draft Solution)', 1),
        ('ทดสอบอุปกรณ์เซนเซอร์และระบบรวม (Complete Solution)', 1),
        ('ประชุมรีวิวความถูกต้องทางเทคนิคภายใน (Internal Verification)', 2),
        ('ปรับปรุงแก้ไขจุดบกพร่องของโซลูชันให้สมบูรณ์ 100%', 2),
        ('ส่งมอบโซลูชันที่ Verify แล้วให้ทีม Sale / Present ผู้บริหาร', 3),
        ('นำเสนอแผนงาน/โซลูชันให้ลูกค้าฟัง', 3),
        ('รับ Feedback เพื่อปรับปรุง', 3),
        ('ลูกค้ายืนยันความเข้าใจโซลูชันว่าตรงความต้องการ', 3),
        ('เข้าสำรวจเครื่องจักรโดยละเอียดเพื่อทำ BOM', 4),
        ('ถอดแบบ BOM แยก SW/HW ให้ชัดเจน', 4),
        ('ลูกค้าเซ็น/อีเมลยืนยันสเปก BOM', 4),
        ('ประเมินราคา/นำ BOM ไปคำนวณต้นทุนและราคาขาย', 4),
        ('รวบรวมข้อมูลทำ Proposal', 5),
        ('ตรวจสอบและอนุมัติขั้นสุดท้ายโดยผู้บริหาร (Final Review)', 5),
        ('จัดส่ง Proposal ฉบับสมบูรณ์ให้ Sale / ลุกค้า', 5),
        ('ติดตามผลจากลูกค้า (Follow-up)', 6),
        ('อัปเดตสถานะสุดท้าย (รอ/ ชนะ/ แพ้-ยกเลิก)', 6);

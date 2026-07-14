"""Seed demo data for Project-Tracking.

Creates demo users and a spread of projects with tasks, tags and comments so
every view has something to show. Idempotent-ish: it clears and recreates the
schema, so only run it against a throwaway/dev database.
"""
from datetime import date, timedelta

from sqlalchemy import text

from . import extensions
from .extensions import Session
from .models import (
    Base,
    Comment,
    LookupType,
    LookupValue,
    ProcessTag,
    Project,
    PTemplate,
    PTrack,
    Tag,
    Task,
    User,
)


def _ensure_schema(engine):
    """Create the ``pjtrk`` schema on PostgreSQL if it's missing.

    SQLAlchemy is configured with ``search_path=pjtrk`` (see
    ``extensions.init_engine``), so every CREATE TABLE expects that schema to
    exist. On a brand-new database it doesn't yet — bootstrap it here so the
    seed flow works on a fresh device without first running ``init_db.sql``.
    No-op on SQLite/MSSQL.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS pjtrk"))
        conn.commit()


# ── Reference data ────────────────────────────────────────────────────────────

# Process stages with their day budgets; seeded into process_tags.
DEMO_PROCESS_TAGS = [
    (1, "Site Survey & Draft",  13),
    (2, "Verify Solution",       6),
    (3, "Presentation",          6),
    (4, "BOM List & Costing",    6),
    (5, "Executive Review",      6),
    (6, "Post-Submission",      13),
]

# Default process/task checklist — 20 tasks seeded into ptemplate and then
# bulk-copied into every project's ptrack on creation.
# Format: (task_text, processid)
DEMO_PTEMPLATE = [
    ("รับโจทย์ / เข้าสำรวจหน้างาน / บันทึกความต้องการลูกค้า (Requirement)", 1),
    ("วิเคราะห์ปัญหาหลัก (Pain Point)", 1),
    ("อัปเดตข้อมูลให้ทีมภายในทราบ ภายใน 1-3 วันแรก", 1),
    ("ทำร่างโซลูชัน (Draft Solution)", 1),
    ("ทดสอบอุปกรณ์เซนเซอร์และระบบรวม (Complete Solution)", 1),
    ("ประชุมรีวิวความถูกต้องทางเทคนิคภายใน (Internal Verification)", 2),
    ("ปรับปรุงแก้ไขจุดบกพร่องของโซลูชันให้สมบูรณ์ 100%", 2),
    ("ส่งมอบโซลูชันที่ Verify แล้วให้ทีม Sale / Present ผู้บริหาร", 3),
    ("นำเสนอแผนงาน/โซลูชันให้ลูกค้าฟัง", 3),
    ("รับ Feedback เพื่อปรับปรุง", 3),
    ("ลูกค้ายืนยันความเข้าใจโซลูชันว่าตรงความต้องการ", 3),
    ("เข้าสำรวจเครื่องจักรโดยละเอียดเพื่อทำ BOM", 4),
    ("ถอดแบบ BOM แยก SW/HW ให้ชัดเจน", 4),
    ("ลูกค้าเซ็น/อีเมลยืนยันสเปก BOM", 4),
    ("ประเมินราคา/นำ BOM ไปคำนวณต้นทุนและราคาขาย", 4),
    ("รวบรวมข้อมูลทำ Proposal", 5),
    ("ตรวจสอบและอนุมัติขั้นสุดท้ายโดยผู้บริหาร (Final Review)", 5),
    ("จัดส่ง Proposal ฉบับสมบูรณ์ให้ Sale / ลุกค้า", 5),
    ("ติดตามผลจากลูกค้า (Follow-up)", 6),
    ("อัปเดตสถานะสุดท้าย (รอ/ ชนะ/ แพ้-ยกเลิก)", 6),
]

# Format: (display_name, email, password, role, employee_user_id)
DEMO_USERS = [
    ("Admin",                    "admin@scada.local",          "admin123",  "super_admin",  11111),
    ("นายพิชัยวุธ โพธิดอกไม้",  "pichaiwoot.p@scada.local",  "password",  "member", 32123),
    ("นายโอภาส สุ่มเมา",         "opast.s@scada.local",       "password",  "member", 32221),
    ("นายปัญญา เจริญผล",         "panya.c@scada.local",       "password",  "member", 32842),
]

# Format: (name, domain, customer, pm, status, value, progress, fy, priority, days_to_due, team_size, complexity)
# pm must match a name from DEMO_USERS. team_size/complexity seed the Summaries
# pipeline (complexity 1-10) with a deliberate spread so demo grades cover A-D.
DEMO_PROJECTS = [
    ("Kiosk ตรวจสอบเอกสาร R1",        "Robot",        "กรมสรรพสามิต", "นายโอภาส สุ่มเมา",        "Pre-Sale",         40_000_000,  0,   "70", "high",     90,   8,  7),
    ("Battery Monitoring",              "IoT",          "กรมสรรพสามิต", "นายพิชัยวุธ โพธิดอกไม้",  "Pre-Sale",         25_000_000,  5,   "70", "medium",  120,   5,  4),
    ("AI Mobile Lab 5 ใน 7",           "Vision Sensor","เอกชน",         "นายปัญญา เจริญผล",        "Pre-Sale",         28_000_000, 10,   "71", "medium",  200,   6,  8),
    ("Vision Replacement P2",           "Vision Sensor","โรงงาน X",      "นายโอภาส สุ่มเมา",        "Pre-Sale",         22_000_000,  8,   "71", "low",     210,   4,  5),
    ("Marker Phase 4",                  "PLC",          "โรงงาน Y",      "นายพิชัยวุธ โพธิดอกไม้",  "Pre-Sale",         40_000_000, 12,   "70", "high",     60,   9,  6),
    ("Marker Phase 5",                  "PLC",          "โรงงาน Y",      "นายโอภาส สุ่มเมา",        "Project Initiation",17_000_000, 30,   "70", "medium",   45,   5,  5),
    ("Vision Replacement P3 10 ใน 30", "Vision Sensor","โรงงาน X",      "นายพิชัยวุธ โพธิดอกไม้",  "Project Initiation",75_000_000, 35,   "71", "critical",  30,  12,  9),
    ("E-STAMP",                         "IoT",          "กรมสรรพสามิต", "นายปัญญา เจริญผล",        "Project Initiation",60_000_000, 40,   "70", "high",     -5,  10,  6),
    ("AI โครงการอัตโนมัติ",             "AI",           "เอกชน",         "นายพิชัยวุธ โพธิดอกไม้",  "award",             9_000_000, 55,   "70", "medium",   25,   4,  7),
    ("Mobile Lab P2",                   "Vision Sensor","เอกชน",         "นายโอภาส สุ่มเมา",        "award",            12_000_000, 60,   "71", "low",      75,   3,  3),
    ("AI Chatbot กรมสรรพสามิต",        "AI",           "กรมสรรพสามิต", "นายพิชัยวุธ โพธิดอกไม้",  "Project Delivery",  8_000_000, 75,   "69", "medium",   10,   6,  5),
    ("T-VER บริการคาร์บอน",            "IoT",          "เอกชน",         "Admin",                   "Project Delivery", 30_000_000, 80,   "69", "high",     -2,   8,  6),
    ("AI โครงการ DEMO",                "Robot",        "เอกชน",         "นายปัญญา เจริญผล",        "Project Delivery",  5_000_000, 70,   "70", "low",      18,   3,  4),
    ("Meter Modernization",             "PLC",          "กรมสรรพสามิต", "นายปัญญา เจริญผล",        "Completed",        95_000_000, 100,  "69", "high",    -40,  15,  8),
]

DEMO_TAGS = {
    "กรมสรรพสามิต": "#3b82f6",
    "เอกชน":        "#10b981",
    "เร่งด่วน":     "#ef4444",
    "R&D":           "#8b5cf6",
}

# BOM category taxonomy — powers the BOM page's Category -> Type filter.
# Snapshot of the dev/prod reference data so a reseed doesn't lose it (see
# CLAUDE.md "Summaries pipeline" note on Base.metadata not adding columns —
# same concern applies here: drop_all/create_all wipes these rows).
# Format: (code, name, description)
DEMO_LOOKUP_TYPES = [
    ("PC",              "PC",               "PC"),
    ("PLC",             "PLC",              "PLC"),
    ("CAMERA",          "Camera",           "Camera"),
    ("LENS",            "Lens",             "Lens"),
    ("SENSOR",          "Sensor",           "Sensor"),
    ("CABLE",           "Cable",            "Cable"),
    ("LIGHTING",        "Lighting",         "Lighting"),
    ("SERVER",          "Server",           "Server"),
    ("FIREWALL",        "Firewall",         "Firewall"),
    ("UPS",             "UPS",              "UPS"),
    ("ETHERNET_SWITCH", "Ethernet switch",  "Ethernet switch"),
    ("MONITOR_SCREEN",  "Monitor screen",   "Monitor screen"),
    ("ACCESSORY",       "Accessory",        "Accessory"),
    ("ETC",             "etc.",             "etc."),
]

# Format: (type_code, value_code, display_name, sort_order)
DEMO_LOOKUP_VALUES = [
    ("PC", "I3", "i3", 1),
    ("PC", "I5", "i5", 1),
    ("PC", "I7", "i7", 1),
    ("PC", "I9", "i9", 1),
    ("PLC", "IQF", "iQ-F", 2),
    ("PLC", "IQR", "iQ-R", 2),
    ("CAMERA", "INDUSTRIAL_CAM", "Industrial camera", 3),
    ("CAMERA", "READER_CAM", "Reader camera", 3),
    ("CAMERA", "SMART_CAM", "Smart camera", 3),
    ("LENS", "AMOUNT", "A-mount", 4),
    ("LENS", "CMOUNT", "C-mount", 4),
    ("LENS", "FMOUNT", "F-mount", 4),
    ("LENS", "NORM_MOUNT", "Normal-mount", 4),
    ("SENSOR", "CAPACITIVE_PROXIMITY", "Capacitive prox.", 5),
    ("SENSOR", "DIFFUSE", "Diffuse sensor", 5),
    ("SENSOR", "INDUCTIVE_PROXIMITY", "Inductive prox.", 5),
    ("SENSOR", "L_DISPLACEMENT", "Laser displacement (Range)", 5),
    ("SENSOR", "PHOTOELECTRIC", "Photoelectric sensor", 5),
    ("SENSOR", "TEMP", "Temp. sensor", 5),
    ("SENSOR", "THROUGH_BEAM", "Through-beam sensor", 5),
    ("SENSOR", "TORQUE", "Torque", 5),
    ("CABLE", "COM", "Com", 6),
    ("CABLE", "IO_POWER", "I/O,Power", 6),
    ("LIGHTING", "ฺBAR", "Bar-light", 7),
    ("LIGHTING", "DOME", "Dome-light", 7),
    ("LIGHTING", "RING", "Ring-light", 7),
    ("LIGHTING", "UV", "UV-light", 7),
    ("SERVER", "FIREWALL", "Firewall", 8),
    ("FIREWALL", "10K", "10K", 9),
    ("FIREWALL", "3K", "3K", 9),
    ("FIREWALL", "6K", "6K", 9),
    ("UPS", "16P", "16 Ports", 10),
    ("UPS", "24P", "24 Ports", 10),
    ("UPS", "8P", "8 Ports", 10),
    ("ETHERNET_SWITCH", "MONITOR", "Display/Monitoring", 11),
    ("ETHERNET_SWITCH", "HMI", "HMI screen", 11),
]


def seed():
    engine = extensions.engine

    _ensure_schema(engine)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    s = Session()

    # Lookup taxonomy (BOM Category -> Type filter). Types first so values can
    # resolve their parent's freshly-assigned id.
    lookup_types = {}
    for code, name, description in DEMO_LOOKUP_TYPES:
        lt = LookupType(code=code, name=name, description=description)
        s.add(lt)
        lookup_types[code] = lt
    s.flush()
    for type_code, value_code, display_name, sort_order in DEMO_LOOKUP_VALUES:
        s.add(LookupValue(
            lookup_type_id=lookup_types[type_code].id,
            code=value_code,
            display_name=display_name,
            sort_order=sort_order,
        ))

    # Process tags (canonical stage order + day budgets).
    seen_processids = set()
    for processid, process, day_range in DEMO_PROCESS_TAGS:
        if processid not in seen_processids:
            seen_processids.add(processid)
            s.add(ProcessTag(processid=processid, process=process, day_range=day_range))

    # Process template checklist (20 tasks — bulk-copied into each project's ptrack).
    for task_text, processid in DEMO_PTEMPLATE:
        s.add(PTemplate(task=task_text, processid=processid))
    s.flush()

    # Build a lookup from processid → process name for ptrack seeding.
    process_name_by_id = {pid: name for pid, name, _ in DEMO_PROCESS_TAGS}

    # Users — create via ORM, then set the employee user_id via raw SQL because
    # the user_id column exists on the DB table but is not declared in the ORM model.
    users = {}
    uid_map: dict[str, int] = {}   # name → employee user_id
    for display_name, email, pw, role, emp_id in DEMO_USERS:
        u = User(name=display_name, email=email, role=role)
        u.set_password(pw)
        s.add(u)
        users[display_name] = u
        uid_map[display_name] = emp_id
    s.flush()

    # Set employee IDs now that ORM-assigned PKs are available.
    for display_name, emp_id in uid_map.items():
        u = users[display_name]
        s.execute(
            text("UPDATE pjtrk.users SET user_id = :uid WHERE id = :id"),
            {"uid": emp_id, "id": u.id},
        )

    tags = {}
    for name, color in DEMO_TAGS.items():
        t = Tag(name=name, color=color)
        s.add(t)
        tags[name] = t
    s.flush()

    admin = users["Admin"]
    today = date.today()
    total_tasks = len(DEMO_PTEMPLATE)

    for (
        name, domain, customer, pm, status, value, progress, fy, priority, days,
        team_size, complexity,
    ) in DEMO_PROJECTS:
        p = Project(
            name=name, domain=domain, customer=customer, pm=pm, status=status,
            value=value, progress=progress, fiscal_year=fy, priority=priority,
            team_size=team_size, complexity=complexity,
            start_date=today - timedelta(days=30),
            due_date=today + timedelta(days=days),
            owner_id=users.get(pm, admin).id,
            description=f"{domain} project for {customer}.",
        )
        p.tags = [tags[customer]] if customer in tags else []
        if priority in ("high", "critical"):
            p.tags.append(tags["เร่งด่วน"])
        p.tasks = [
            Task(title="กำหนดขอบเขตงาน (SOW)", done=progress > 10, assignee=pm),
            Task(title="ออกแบบระบบ",            done=progress > 40, assignee=pm),
            Task(title="ติดตั้งและทดสอบ",       done=progress > 80),
        ]
        s.add(p)
        s.flush()
        p.comments = [
            Comment(project_id=p.id, user_id=admin.id, body="เริ่มต้นโครงการแล้ว"),
        ]
        # Mirror create_project: copy the full ptemplate checklist into ptrack.
        # Mark tasks as checked proportionally to the project's progress %.
        for idx, (task_text, processid) in enumerate(DEMO_PTEMPLATE):
            task_progress_threshold = (idx / total_tasks) * 100
            s.add(PTrack(
                project_id=p.id,
                process=process_name_by_id.get(processid),
                task=task_text,
                pm=pm,
                checked=progress > task_progress_threshold,
            ))

    s.commit()
    print(
        f"Seeded {len(DEMO_USERS)} users and {len(DEMO_PROJECTS)} projects.\n"
        "Login with admin@scada.local / admin123"
    )


if __name__ == "__main__":
    seed()

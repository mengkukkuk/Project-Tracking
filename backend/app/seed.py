"""Seed demo data for Project-Tracking.

Creates a default admin user and a spread of projects with tasks, tags and
comments so every view has something to show. Idempotent-ish: it clears and
recreates the schema, so only run it against a throwaway/dev database.
"""
from datetime import date, timedelta

from . import extensions
from .extensions import Session
from .models import Base, Comment, Project, Tag, Task, User

DEMO_USERS = [
    ("Admin", "admin@scada.local", "admin123", "admin"),
    ("นายเอ", "a@scada.local", "password", "member"),
    ("นายบี", "b@scada.local", "password", "member"),
    ("นายซี", "c@scada.local", "password", "member"),
]

# name, domain, customer, pm, status, value, progress, fy, priority, days_to_due
DEMO_PROJECTS = [
    ("Kiosk ตรวจสอบเอกสาร R1", "Robot", "กรมสรรพสามิต", "นายเอ", "Pre-Sale", 40_000_000, 0, "70", "high", 90),
    ("Battery Monitoring", "IoT", "กรมสรรพสามิต", "นายบี", "Pre-Sale", 25_000_000, 5, "70", "medium", 120),
    ("AI Mobile Lab 5 ใน 7", "Vision Sensor", "เอกชน", "นายซี", "Pre-Sale", 28_000_000, 10, "71", "medium", 200),
    ("Vision Replacement P2", "Vision Sensor", "โรงงาน X", "นายเอ", "Pre-Sale", 22_000_000, 8, "71", "low", 210),
    ("Marker Phase 4", "PLC", "โรงงาน Y", "นายบี", "Pre-Sale", 40_000_000, 12, "70", "high", 60),
    ("Marker Phase 5", "PLC", "โรงงาน Y", "นายเอ", "Project Initiation", 17_000_000, 30, "70", "medium", 45),
    ("Vision Replacement P3 10 ใน 30", "Vision Sensor", "โรงงาน X", "นายบี", "Project Initiation", 75_000_000, 35, "71", "critical", 30),
    ("E-STAMP", "IoT", "กรมสรรพสามิต", "นายซี", "Project Initiation", 60_000_000, 40, "70", "high", -5),
    ("AI โครงการอัตโนมัติ", "AI", "เอกชน", "นายเอ", "Award", 9_000_000, 55, "70", "medium", 25),
    ("Mobile Lab P2", "Vision Sensor", "เอกชน", "นายบี", "Award", 12_000_000, 60, "71", "low", 75),
    ("AI Chatbot กรมสรรพสามิต", "AI", "กรมสรรพสามิต", "นายซี", "Project Delivery", 8_000_000, 75, "69", "medium", 10),
    ("T-VER บริการคาร์บอน", "IoT", "เอกชน", "นายเอ", "Project Delivery", 30_000_000, 80, "69", "high", -2),
    ("AI โครงการ DEMO", "Robot", "เอกชน", "นายบี", "Project Delivery", 5_000_000, 70, "70", "low", 18),
    ("Meter Modernization", "PLC", "กรมสรรพสามิต", "นายซี", "Completed", 95_000_000, 100, "69", "high", -40),
]

DEMO_TAGS = {
    "กรมสรรพสามิต": "#3b82f6",
    "เอกชน": "#10b981",
    "เร่งด่วน": "#ef4444",
    "R&D": "#8b5cf6",
}


def seed():
    engine = extensions.engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = Session()

    users = {}
    for name, email, pw, role in DEMO_USERS:
        u = User(name=name, email=email, role=role)
        u.set_password(pw)
        s.add(u)
        users[name] = u
    s.flush()

    tags = {}
    for name, color in DEMO_TAGS.items():
        t = Tag(name=name, color=color)
        s.add(t)
        tags[name] = t
    s.flush()

    admin = users["Admin"]
    today = date.today()
    for (
        name, domain, customer, pm, status, value, progress, fy, priority, days
    ) in DEMO_PROJECTS:
        p = Project(
            name=name, domain=domain, customer=customer, pm=pm, status=status,
            value=value, progress=progress, fiscal_year=fy, priority=priority,
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
            Task(title="ออกแบบระบบ", done=progress > 40, assignee=pm),
            Task(title="ติดตั้งและทดสอบ", done=progress > 80),
        ]
        s.add(p)
        s.flush()
        p.comments = [
            Comment(project_id=p.id, user_id=admin.id, body="เริ่มต้นโครงการแล้ว"),
        ]

    s.commit()
    print(
        f"Seeded {len(DEMO_USERS)} users and {len(DEMO_PROJECTS)} projects.\n"
        "Login with admin@scada.local / admin123"
    )


if __name__ == "__main__":
    seed()

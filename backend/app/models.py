"""SQLAlchemy ORM models.

The schema is intentionally portable across SQLite (dev), PostgreSQL and MSSQL:
no DB-specific column types are used. Money is stored as ``Numeric`` and exposed
as ``float`` in the API.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship
from werkzeug.security import check_password_hash, generate_password_hash

Base = declarative_base()

# Canonical pipeline stages — order matters for the funnel.
STAGES = ["Pre-Sale", "Project Initiation", "Award", "Project Delivery", "Completed"]
PRIORITIES = ["low", "medium", "high", "critical"]
ROLES = ["admin", "member"]

# Many-to-many: projects <-> tags
project_tags = Table(
    "project_tags",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many: projects <-> project managers (users)
project_pms = Table(
    "project_pms",
    Base.metadata,
    Column("project_id", ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


def _iso(value):
    return value.isoformat() if value else None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(16), nullable=False, default="member")
    created_at = Column(DateTime, default=func.now())

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "createdAt": _iso(self.created_at),
        }


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(48), nullable=False, unique=True)
    color = Column(String(16), default="#64748b")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": self.color}


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    domain = Column(String(64))            # Vision Sensor, Robot, PLC, IoT, AI
    customer = Column(String(255))
    pm = Column(String(128))               # project manager (free text)
    status = Column(String(64), nullable=False, default="Pre-Sale")
    priority = Column(String(16), nullable=False, default="medium")
    value = Column(Numeric(14, 2), default=0)   # THB
    progress = Column(Integer, default=0)       # 0-100
    fiscal_year = Column(String(8))             # "69", "70", "71", "future"
    start_date = Column(Date)
    due_date = Column(Date)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    owner = relationship("User")
    tags = relationship("Tag", secondary=project_tags, lazy="selectin")
    pms = relationship("User", secondary=project_pms, lazy="selectin", order_by="User.name")
    tasks = relationship(
        "Task", back_populates="project", cascade="all, delete-orphan", lazy="selectin"
    )
    comments = relationship(
        "Comment",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Comment.created_at.desc()",
    )
    activities = relationship(
        "Activity",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Activity.created_at.desc()",
    )
    ptracks = relationship(
        "PTrack", backref="project", cascade="all, delete-orphan", lazy="selectin"
    )

    def to_dict(self, detail: bool = False):
        tasks = list(self.tasks)
        done = sum(1 for t in tasks if t.done)
        ptracks = list(self.ptracks)
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "customer": self.customer,
            "pm": self.pm,
            "pms": [{"id": u.id, "name": u.name} for u in self.pms],
            "pmIds": [u.id for u in self.pms],
            "status": self.status,
            "priority": self.priority,
            "value": float(self.value or 0),
            "progress": self.progress or 0,
            "fiscalYear": self.fiscal_year,
            "startDate": _iso(self.start_date),
            "dueDate": _iso(self.due_date),
            "ownerId": self.owner_id,
            "owner": self.owner.to_dict() if self.owner else None,
            "tags": [t.to_dict() for t in self.tags],
            "taskCount": len(tasks),
            "taskDone": done,
            "processCount": len(ptracks),
            "processDone": sum(1 for r in ptracks if r.checked),
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }
        if detail:
            data["tasks"] = [t.to_dict() for t in sorted(tasks, key=lambda x: x.id)]
            data["comments"] = [c.to_dict() for c in self.comments]
            data["activities"] = [a.to_dict() for a in self.activities[:50]]
        return data


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(255), nullable=False)
    done = Column(Boolean, default=False)
    assignee = Column(String(128))
    due_date = Column(Date)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "title": self.title,
            "done": bool(self.done),
            "assignee": self.assignee,
            "dueDate": _iso(self.due_date),
            "createdAt": _iso(self.created_at),
        }


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="comments")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "body": self.body,
            "user": self.user.to_dict() if self.user else None,
            "createdAt": _iso(self.created_at),
        }


class Activity(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    action = Column(String(64), nullable=False)   # created, updated, moved, ...
    detail = Column(String(512))
    created_at = Column(DateTime, default=func.now())

    project = relationship("Project", back_populates="activities")
    user = relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "action": self.action,
            "detail": self.detail,
            "user": self.user.to_dict() if self.user else None,
            "createdAt": _iso(self.created_at),
        }


class PTemplate(Base):
    """Process/task template — bulk-inserted into ptrack on new project."""
    __tablename__ = "ptemplate"

    id = Column(Integer, primary_key=True)
    task = Column(Text)
    processid = Column(Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "task": self.task,
            "processId": self.processid,
        }


class ProcessTag(Base):
    __tablename__ = "process_tags"

    id = Column(Integer, primary_key=True)
    processid = Column(Integer)
    process = Column(Text)
    day_range = Column(Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "processId": self.processid,
            "process": self.process,
            "dayRange": self.day_range,
        }


class PTrack(Base):
    """Per-project process tracking (seeded from ptemplate)."""
    __tablename__ = "ptrack"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    process = Column(Text)
    pm = Column(Text)
    start_date = Column(Date)
    due_date = Column(Date)
    task = Column(Text)
    status = Column(Text)
    checked = Column("check", Boolean, default=False)
    reference = Column(Text)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "process": self.process,
            "pm": self.pm,
            "startDate": _iso(self.start_date),
            "dueDate": _iso(self.due_date),
            "task": self.task,
            "status": self.status,
            "checked": bool(self.checked),
            "reference": self.reference,
        }


class SurveyReport(Base):
    __tablename__ = "survey_report"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    date = Column(Date)
    department = Column(Text)
    requirement = Column(Text)
    issue = Column(Text)
    limitation = Column(Text)
    result = Column(Text)
    conclude = Column(Text)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "date": _iso(self.date),
            "department": self.department,
            "requirement": self.requirement,
            "issue": self.issue,
            "limitation": self.limitation,
            "result": self.result,
            "conclude": self.conclude,
        }


class CustomerMom(Base):
    __tablename__ = "customer_mom"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    date = Column(Date)
    participant = Column(Text)
    topic = Column(Text)
    concerns = Column(Text)
    conclude = Column(Text)
    todo = Column(Text)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "date": _iso(self.date),
            "participant": self.participant,
            "topic": self.topic,
            "concerns": self.concerns,
            "conclude": self.conclude,
            "todo": self.todo,
        }


class BomAndCosting(Base):
    __tablename__ = "bom_and_costing"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    date_approve = Column(Date)
    category = Column(Text)
    device_name = Column(Text)
    version = Column(Text)
    spec = Column(Text)
    quantity = Column(Integer)
    unit = Column(Text)
    position = Column("position", Text)
    unit_price = Column(Integer)
    total_price = Column(Integer)
    lead_time = Column(Integer)
    supplier = Column(Text)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "dateApprove": _iso(self.date_approve),
            "category": self.category,
            "deviceName": self.device_name,
            "version": self.version,
            "spec": self.spec,
            "quantity": self.quantity,
            "unit": self.unit,
            "position": self.position,
            "unitPrice": self.unit_price,
            "totalPrice": self.total_price,
            "leadTime": self.lead_time,
            "supplier": self.supplier,
        }


class InternalVerification(Base):
    __tablename__ = "internal_verification"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    date = Column(Date)
    approver = Column(Text)
    test_system = Column(Text)
    test_result = Column(Text)
    defected = Column(Text)
    solution = Column(Text)
    status = Column(Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "date": _iso(self.date),
            "approver": self.approver,
            "testSystem": self.test_system,
            "testResult": self.test_result,
            "defected": self.defected,
            "solution": self.solution,
            "status": bool(self.status),
        }


class ExceptionLog(Base):
    __tablename__ = "exception_log"

    id = Column(Integer, primary_key=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    date = Column(Date)
    informer = Column(Text)
    order_list = Column(Text)
    effect_price = Column(Text)
    effect_tech = Column(Text)
    date_new_bom = Column(Date)
    date_new_pps = Column(Date)

    def to_dict(self):
        return {
            "id": self.id,
            "projectId": self.project_id,
            "userId": self.user_id,
            "date": _iso(self.date),
            "informer": self.informer,
            "orderList": self.order_list,
            "effectPrice": self.effect_price,
            "effectTech": self.effect_tech,
            "dateNewBom": _iso(self.date_new_bom),
            "dateNewPps": _iso(self.date_new_pps),
        }

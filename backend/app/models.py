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

    def to_dict(self, detail: bool = False):
        tasks = list(self.tasks)
        done = sum(1 for t in tasks if t.done)
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "customer": self.customer,
            "pm": self.pm,
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

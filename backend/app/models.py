"""SQLAlchemy ORM models.

The schema is intentionally portable across SQLite (dev), PostgreSQL, and MSSQL:
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

from .permissions import permissions_for, role_has_permission

Base = declarative_base()

# Canonical pipeline stages — order matters for the funnel.
STAGES = ["Pre-Sale", "Project Initiation", "award", "Project Delivery", "Completed"]
PRIORITIES = ["low", "medium", "high", "critical"]
# Ordered most-privileged first. super_admin is the system owner (wildcard
# permissions); admin is org-scoped full access; member is own-record CRUD.
ROLES = ["super_admin", "admin", "member"]
# Roles that pass an owner-or-elevated check regardless of row ownership.
ELEVATED_ROLES = ("super_admin", "admin")


def derived_status(progress: int) -> str:
    """Map a project's progress % to its pipeline stage.

    Status is no longer user-editable — it's a 5-bucket projection of the
    progress bar (which itself is driven by the process checklist):
        0-19   -> Pre-Sale
        20-39  -> Project Initiation
        40-59  -> award
        60-79  -> Project Delivery
        80-100 -> Completed
    """
    p = max(0, min(100, int(progress or 0)))
    if p < 20:
        return STAGES[0]
    if p < 40:
        return STAGES[1]
    if p < 60:
        return STAGES[2]
    if p < 80:
        return STAGES[3]
    return STAGES[4]

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

    def has_permission(self, perm: str) -> bool:
        """Authoritative capability check — resolved from the *live* DB role at
        request time, never from a (possibly stale) JWT claim. Wildcard-aware.
        """
        return role_has_permission(self.role, perm)

    def to_dict(self):
        # ``permissions`` is advisory: the SPA uses it to hide UI it can't act
        # on. It is NEVER the source of truth for a backend check — every guard
        # re-derives from the live role via has_permission().
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "permissions": sorted(permissions_for(self.role)),
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
    team_size = Column(Integer)                 # Summaries pipeline input, nullable
    complexity = Column(Integer)                # Summaries pipeline input, 1-10, nullable
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
        # Derive the live progress % the same way the frontend does (process
        # checklist preferred, task counts as fallback, then the persisted
        # progress column), then bucket it into a stage for the badge.
        ptotal = len(ptracks)
        pdone = sum(1 for r in ptracks if r.checked)
        if ptotal:
            live_progress = round((pdone / ptotal) * 100)
        elif tasks:
            live_progress = round((done / len(tasks)) * 100)
        else:
            live_progress = int(self.progress or 0)
        status = derived_status(live_progress)
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "customer": self.customer,
            "pm": self.pm,
            "pms": [{"id": u.id, "name": u.name} for u in self.pms],
            "pmIds": [u.id for u in self.pms],
            "status": status,
            "priority": self.priority,
            "value": float(self.value or 0),
            "progress": self.progress or 0,
            "teamSize": self.team_size,
            "complexity": self.complexity,
            "fiscalYear": self.fiscal_year,
            "startDate": _iso(self.start_date),
            "dueDate": _iso(self.due_date),
            "ownerId": self.owner_id,
            "owner": self.owner.to_dict() if self.owner else None,
            "tags": [t.to_dict() for t in self.tags],
            "taskCount": len(tasks),
            "taskDone": done,
            "processCount": ptotal,
            "processDone": pdone,
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
    surveyor = Column(Text)

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
            "surveyor": self.surveyor,
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


class BomList(Base):
    """Saved, named selection of bom_and_costing rows for a target project.

    Items are FK references — edits to a source row flow through on next read,
    and deleting a source row cascades the corresponding list-item away.
    """

    __tablename__ = "bom_lists"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    items = relationship(
        "BomListItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self):
        """Bare serialization. The API layer enriches with projectName / items[]
        (it has the Session) so the model stays free of DB lookups.
        """
        return {
            "id": self.id,
            "name": self.name,
            "projectId": self.project_id,
            "ownerId": self.owner_id,
            "itemCount": len(self.items),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class BomListItem(Base):
    """Join row: bom_list <-> bom_and_costing (FK reference, composite PK)."""

    __tablename__ = "bom_list_items"

    list_id = Column(
        Integer,
        ForeignKey("bom_lists.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bom_id = Column(
        Integer,
        ForeignKey("bom_and_costing.id", ondelete="CASCADE"),
        primary_key=True,
    )

    parent = relationship("BomList", back_populates="items")
    bom = relationship("BomAndCosting", lazy="joined")

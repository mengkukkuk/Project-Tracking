"""Tasks (checklist items) belonging to a project."""
from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Project, Task
from ..validation import (
    bool_field,
    date_field,
    require_dict,
    str_field,
)
from .helpers import log_activity, require_owner_or_admin

bp = Blueprint("tasks", __name__, url_prefix="/api")


@bp.post("/projects/<int:pid>/tasks")
@jwt_required()
def create_task(pid):
    p = Session.get(Project, pid)
    if not p:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    data = require_dict(request.get_json(silent=True))
    task = Task(
        project_id=pid,
        title=str_field(data, "title", required=True, max_len=255),
        assignee=str_field(data, "assignee", max_len=128),
        due_date=date_field(data, "dueDate"),
        done=bool_field(data, "done", default=False),
    )
    Session.add(task)
    log_activity(pid, "task", f"Added task “{task.title}”", current_user())
    Session.commit()
    return task.to_dict(), 201


@bp.patch("/tasks/<int:tid>")
@jwt_required()
def update_task(tid):
    task = Session.get(Task, tid)
    if not task:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    data = require_dict(request.get_json(silent=True))
    if "title" in data:
        task.title = str_field(data, "title", required=True, max_len=255)
    if "assignee" in data:
        task.assignee = str_field(data, "assignee", max_len=128)
    if "dueDate" in data:
        task.due_date = date_field(data, "dueDate")
    if "done" in data:
        task.done = bool_field(data, "done", default=False)
    Session.commit()
    return task.to_dict()


@bp.delete("/tasks/<int:tid>")
@jwt_required()
def delete_task(tid):
    task = Session.get(Task, tid)
    if not task:
        return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404
    user = current_user()
    project = Session.get(Project, task.project_id)
    denied = require_owner_or_admin(user, project.owner_id if project else None)
    if denied:
        return denied
    Session.delete(task)
    Session.commit()
    return "", 204

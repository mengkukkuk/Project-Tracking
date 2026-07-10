"""Per-project document uploads (PDF only).

Stores quotation / technical datasheet ("tds") / result PDFs on disk under
``DOCSTORE_DIR/<project_id>/<doc_type>/`` with server-generated uuid filenames;
metadata (including the original, possibly-unicode filename) lives in the
``project_documents`` table. Follows the records.py authz convention:
any authenticated user may upload/list/download, delete is owner-or-admin.
"""
import os
import re
import shutil
from uuid import uuid4

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Project, ProjectDocument
from ..validation import ValidationError
from .helpers import log_activity, require_owner_or_admin

bp = Blueprint("documents", __name__, url_prefix="/api")

# doc_type slug -> human label (used in activity log messages)
DOC_TYPES = {
    "quotation": "quotation",
    "tds": "technical datasheet",
    "result": "result",
}
PDF_MAGIC = b"%PDF-"


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _docstore_root():
    return current_app.config["DOCSTORE_DIR"]


def _doc_dir(pid, doc_type):
    path = os.path.join(_docstore_root(), str(pid), doc_type)
    os.makedirs(path, exist_ok=True)
    return path


def _doc_path(doc):
    return os.path.join(
        _docstore_root(), str(doc.project_id), doc.doc_type, doc.stored_name
    )


def _display_name(filename):
    """Display/download name from the client filename: basename only (some
    browsers send paths, with either separator), trimmed to the column size.
    Deliberately NOT secure_filename — that would strip Thai characters."""
    name = re.split(r"[\\/]", filename or "")[-1].strip()
    return name[:255] or "document.pdf"


def remove_project_docstore(pid):
    """Best-effort removal of a project's whole document folder (used when the
    project itself is deleted). ignore_errors so a locked file on Windows can't
    turn a successful delete into a 500."""
    shutil.rmtree(os.path.join(_docstore_root(), str(pid)), ignore_errors=True)


@bp.get("/projects/<int:pid>/documents")
@jwt_required()
def list_documents(pid):
    """GET /api/projects/<pid>/documents[?type=quotation|tds|result]"""
    if not Session.get(Project, pid):
        return _not_found()
    doc_type = request.args.get("type")
    if doc_type is not None and doc_type not in DOC_TYPES:
        return _not_found()
    query = Session.query(ProjectDocument).filter(ProjectDocument.project_id == pid)
    if doc_type:
        query = query.filter(ProjectDocument.doc_type == doc_type)
    rows = query.order_by(ProjectDocument.id.asc()).all()
    return {"items": [r.to_dict() for r in rows]}


@bp.post("/projects/<int:pid>/documents/<doc_type>")
@jwt_required()
def upload_documents(pid, doc_type):
    """POST /api/projects/<pid>/documents/<doc_type> — multipart upload.

    Accepts one or more PDFs under the ``files`` form key. Every file is
    validated (extension, %PDF magic bytes, non-empty) before anything is
    written, so a request either persists all its files or none of them.
    """
    if doc_type not in DOC_TYPES:
        return _not_found()
    if not Session.get(Project, pid):
        return _not_found()

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        raise ValidationError({"files": "at least one PDF file is required"})

    sizes = []
    for f in files:
        name = _display_name(f.filename)
        if not f.filename.lower().endswith(".pdf"):
            raise ValidationError({"files": f"'{name}': only .pdf files are allowed"})
        head = f.stream.read(len(PDF_MAGIC))
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        if size == 0 or head != PDF_MAGIC:
            raise ValidationError({"files": f"'{name}': not a valid PDF"})
        sizes.append(size)

    user = current_user()
    target_dir = _doc_dir(pid, doc_type)
    created = []
    written = []
    try:
        for f, size in zip(files, sizes):
            doc = ProjectDocument(
                project_id=pid,
                user_id=user.id if user else None,
                doc_type=doc_type,
                original_name=_display_name(f.filename),
                stored_name=uuid4().hex + ".pdf",
                size_bytes=size,
            )
            Session.add(doc)
            created.append(doc)
            path = os.path.join(target_dir, doc.stored_name)
            f.save(path)
            written.append(path)
        log_activity(
            pid,
            "task",
            f"Uploaded {len(created)} {DOC_TYPES[doc_type]} document(s)",
            user,
        )
        Session.commit()
    except Exception:
        Session.rollback()
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return {"items": [d.to_dict() for d in created]}, 201


@bp.get("/documents/<int:doc_id>/download")
@jwt_required()
def download_document(doc_id):
    """GET /api/documents/<doc_id>/download — stream the PDF as an attachment
    under its original filename. Path components are all server-generated
    (int id, whitelisted type, uuid name), so there is no traversal surface."""
    doc = Session.get(ProjectDocument, doc_id)
    if not doc:
        return _not_found()
    path = _doc_path(doc)
    if not os.path.isfile(path):
        return _not_found()
    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=doc.original_name,
        max_age=0,
    )


@bp.delete("/documents/<int:doc_id>")
@jwt_required()
def delete_document(doc_id):
    """DELETE /api/documents/<doc_id> — parent project's owner or admin only.
    The disk file is removed only after the DB delete commits (best effort),
    so a failed transaction can never orphan a row's file."""
    doc = Session.get(ProjectDocument, doc_id)
    if not doc:
        return _not_found()
    user = current_user()
    project = Session.get(Project, doc.project_id)
    denied = require_owner_or_admin(user, project.owner_id if project else None)
    if denied:
        return denied
    path = _doc_path(doc)
    log_activity(
        doc.project_id,
        "task",
        f"Deleted {DOC_TYPES.get(doc.doc_type, 'document')} “{doc.original_name}”",
        user,
    )
    Session.delete(doc)
    Session.commit()
    try:
        os.remove(path)
    except OSError:
        pass
    return "", 204

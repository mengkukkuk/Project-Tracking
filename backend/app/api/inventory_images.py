"""Inventory catalogue images (product photos, gallery — many per item).

Stores images on disk under ``IMAGESTORE_DIR/<inventory_id>/`` with
server-generated uuid filenames; metadata (including the original, possibly
Thai filename) lives in the ``inventory_images`` table.

Authz differs from documents.py on purpose: the inventory catalogue has no
owner column, so there is no ownership scope to apply. Writes are therefore a
plain *capability* gate at the member level (``inventory.create``) for BOTH
upload and delete — any authenticated user who may add a catalogue entry may
also manage its images. (documents.py deletes are owner-or-admin; this is not.)
"""
import os
import re
import shutil
from uuid import uuid4

from flask import Blueprint, current_app, request, send_file
from flask_jwt_extended import jwt_required

from ..auth import current_user
from ..extensions import Session
from ..models import Inventory, InventoryImage
from ..validation import ValidationError
from .helpers import require_permission

bp = Blueprint("inventory_images", __name__, url_prefix="/api")

# ext -> (mime, magic-byte check over the first _HEAD bytes). WEBP needs bytes
# 8..11, so read a 12-byte head for every format.
_MAGIC = {
    "png": ("image/png", lambda b: b[:8] == b"\x89PNG\r\n\x1a\n"),
    "jpg": ("image/jpeg", lambda b: b[:3] == b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", lambda b: b[:3] == b"\xff\xd8\xff"),
    "webp": ("image/webp", lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP"),
    "gif": ("image/gif", lambda b: b[:6] in (b"GIF87a", b"GIF89a")),
}
_HEAD = 12


def _not_found():
    return {"error": {"type": "http", "code": 404, "message": "Not found"}}, 404


def _imagestore_root():
    return current_app.config["IMAGESTORE_DIR"]


def _img_dir(iid):
    path = os.path.join(_imagestore_root(), str(iid))
    os.makedirs(path, exist_ok=True)
    return path


def _img_path(img):
    return os.path.join(_imagestore_root(), str(img.inventory_id), img.stored_name)


def _display_name(filename):
    """Display name from the client filename: basename only (some browsers send
    paths, with either separator), trimmed to the column size. Deliberately NOT
    secure_filename — that would strip Thai characters."""
    name = re.split(r"[\\/]", filename or "")[-1].strip()
    return name[:255] or "image"


def _ext_of(filename):
    return (os.path.splitext(filename or "")[1] or "").lower().lstrip(".")


def remove_inventory_imagestore(iid):
    """Best-effort removal of an inventory item's whole image folder (used when
    the item itself is deleted). ignore_errors so a locked file on Windows can't
    turn a successful delete into a 500."""
    shutil.rmtree(os.path.join(_imagestore_root(), str(iid)), ignore_errors=True)


@bp.get("/inventory/<int:iid>/images")
@jwt_required()
def list_inventory_images(iid):
    """GET /api/inventory/<iid>/images -> {"items": [...]} ordered by id."""
    if not Session.get(Inventory, iid):
        return _not_found()
    rows = (
        Session.query(InventoryImage)
        .filter(InventoryImage.inventory_id == iid)
        .order_by(InventoryImage.id.asc())
        .all()
    )
    return {"items": [r.to_dict() for r in rows]}


@bp.post("/inventory/<int:iid>/images")
@jwt_required()
def upload_inventory_images(iid):
    """POST /api/inventory/<iid>/images — multipart upload (member-gated).

    Accepts one or more images under the ``files`` form key. Every file is
    validated (extension, magic bytes, non-empty) before anything is written,
    so a request either persists all its files or none of them.
    """
    denied = require_permission(current_user(), "inventory.create")
    if denied:
        return denied
    if not Session.get(Inventory, iid):
        return _not_found()

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        raise ValidationError({"files": "at least one image file is required"})

    prepared = []  # (file, ext, mime, size)
    for f in files:
        name = _display_name(f.filename)
        ext = _ext_of(f.filename)
        if ext not in _MAGIC:
            raise ValidationError(
                {"files": f"'{name}': only .png/.jpg/.jpeg/.webp/.gif images are allowed"}
            )
        mime, check = _MAGIC[ext]
        head = f.stream.read(_HEAD)
        f.stream.seek(0, os.SEEK_END)
        size = f.stream.tell()
        f.stream.seek(0)
        if size == 0 or not check(head):
            raise ValidationError({"files": f"'{name}': not a valid {ext} image"})
        prepared.append((f, ext, mime, size))

    user = current_user()
    target_dir = _img_dir(iid)
    created = []
    written = []
    try:
        for f, ext, mime, size in prepared:
            img = InventoryImage(
                inventory_id=iid,
                user_id=user.id if user else None,
                original_name=_display_name(f.filename),
                stored_name=uuid4().hex + "." + ext,
                mime_type=mime,
                size_bytes=size,
            )
            Session.add(img)
            created.append(img)
            path = os.path.join(target_dir, img.stored_name)
            f.save(path)
            written.append(path)
        Session.commit()
    except Exception:
        Session.rollback()
        for path in written:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return {"items": [i.to_dict() for i in created]}, 201


@bp.get("/inventory-images/<int:img_id>")
@jwt_required()
def get_inventory_image(img_id):
    """GET /api/inventory-images/<img_id> — stream the image inline (displayed,
    not an attachment). All path components are server-generated (int id, uuid
    name), so there is no traversal surface."""
    img = Session.get(InventoryImage, img_id)
    if not img:
        return _not_found()
    path = _img_path(img)
    if not os.path.isfile(path):
        return _not_found()
    return send_file(path, mimetype=img.mime_type, max_age=0)


@bp.delete("/inventory-images/<int:img_id>")
@jwt_required()
def delete_inventory_image(img_id):
    """DELETE /api/inventory-images/<img_id> — member-gated (inventory.create).

    Intentionally NOT owner-or-admin like documents: the catalogue has no owner
    column. The disk file is removed only after the DB delete commits (best
    effort), so a failed transaction can never orphan a row's file.
    """
    denied = require_permission(current_user(), "inventory.create")
    if denied:
        return denied
    img = Session.get(InventoryImage, img_id)
    if not img:
        return _not_found()
    path = _img_path(img)
    Session.delete(img)
    Session.commit()
    try:
        os.remove(path)
    except OSError:
        pass
    return "", 204

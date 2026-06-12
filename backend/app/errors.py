"""Centralised JSON error handling.

Every error — validation, auth, not-found, or unexpected — is returned as a
consistent ``{"error": {...}}`` envelope so the frontend can handle them
uniformly.
"""
import logging

from werkzeug.exceptions import HTTPException

from .extensions import Session
from .validation import ValidationError

log = logging.getLogger(__name__)


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def _validation(err):
        return {"error": {"type": "validation", "fields": err.errors}}, 422

    @app.errorhandler(HTTPException)
    def _http(err):
        return {
            "error": {"type": "http", "code": err.code, "message": err.description}
        }, err.code

    @app.errorhandler(Exception)
    def _unhandled(err):
        # Roll back any half-applied transaction so the next request is clean.
        Session.rollback()
        log.exception("Unhandled error: %s", err)
        return {
            "error": {"type": "server", "message": "Internal server error"}
        }, 500

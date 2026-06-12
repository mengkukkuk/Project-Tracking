"""Lightweight request validation helpers.

Kept dependency-free on purpose: a small set of composable validators is enough
for this API and avoids pulling in a heavier schema library. Each helper raises
``ValidationError`` which the error handler turns into a 422 response.
"""
from datetime import date

from .models import PRIORITIES, STAGES


class ValidationError(Exception):
    def __init__(self, errors):
        # errors: dict[field -> message] or a plain string
        self.errors = errors if isinstance(errors, dict) else {"_": errors}
        super().__init__(str(self.errors))


def require_dict(data):
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def str_field(data, key, *, required=False, max_len=None, default=None):
    if key not in data or data[key] is None:
        if required:
            raise ValidationError({key: "is required"})
        return default
    val = data[key]
    if not isinstance(val, str):
        raise ValidationError({key: "must be a string"})
    val = val.strip()
    if required and not val:
        raise ValidationError({key: "must not be empty"})
    if max_len and len(val) > max_len:
        raise ValidationError({key: f"must be at most {max_len} characters"})
    return val


def enum_field(data, key, choices, *, required=False, default=None):
    if key not in data or data[key] is None:
        if required:
            raise ValidationError({key: "is required"})
        return default
    val = data[key]
    if val not in choices:
        raise ValidationError({key: f"must be one of {choices}"})
    return val


def number_field(data, key, *, default=None, minimum=None, maximum=None):
    if key not in data or data[key] is None:
        return default
    try:
        val = float(data[key])
    except (TypeError, ValueError):
        raise ValidationError({key: "must be a number"})
    if minimum is not None and val < minimum:
        raise ValidationError({key: f"must be >= {minimum}"})
    if maximum is not None and val > maximum:
        raise ValidationError({key: f"must be <= {maximum}"})
    return val


def int_field(data, key, *, default=None, minimum=None, maximum=None):
    val = number_field(data, key, default=None, minimum=minimum, maximum=maximum)
    if val is None:
        return default
    return int(val)


def bool_field(data, key, *, default=None):
    if key not in data or data[key] is None:
        return default
    return bool(data[key])


def date_field(data, key, *, default=None):
    if key not in data or data[key] in (None, ""):
        return default
    val = data[key]
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val)[:10])
    except ValueError:
        raise ValidationError({key: "must be an ISO date (YYYY-MM-DD)"})


# Domain-specific shortcuts
def status_field(data, key="status", **kw):
    return enum_field(data, key, STAGES, **kw)


def priority_field(data, key="priority", **kw):
    return enum_field(data, key, PRIORITIES, **kw)

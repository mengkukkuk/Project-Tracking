"""Permission catalog and role -> permission mapping.

RBAC best practice: roles are *collections of permissions*. Backend guards check
a permission (via :meth:`User.has_permission`), never a role name — except for
the intrinsic ownership hierarchy (owner-or-elevated), which stays orthogonal in
``api/helpers.py``.

Two axes, kept separate on purpose:
    * **capability** — "may this role sync sheets / manage templates / assign
      roles at all?" — gated by the permission strings below.
    * **scope** — "own record vs any record" — gated by
      ``require_owner_or_admin`` in ``api/helpers.py``, NOT by permission
      strings. That is why ``projects.update`` is granted to members too: the
      member holds the capability, and ownership narrows the scope.

This module deliberately defines only permissions the app's endpoints actually
exercise (projects / tasks / comments / records / bom_lists / sheets /
templates / users). It is plain data with no imports from ``models`` so it can
be imported by ``models`` without a cycle.
"""

# Capabilities every authenticated member holds. Update/delete are still
# scope-narrowed to owned rows by require_owner_or_admin.
_MEMBER = {
    "projects.read",
    "projects.create",
    "projects.update",
    "projects.delete",
    "tasks.create",
    "tasks.update",
    "tasks.delete",
    "comments.create",
    "comments.delete",
    "records.read",
    "records.create",
    "records.update",
    "records.delete",
    "bom_lists.create",
    "bom_lists.update",
    "bom_lists.delete",
    "users.read",
}

# Admin adds the organization-level capabilities on top of everything a member
# can do. (roles.assign is further constrained in the endpoint: an admin may not
# grant or modify the super_admin role — only a super_admin may.)
_ADMIN = _MEMBER | {
    "sheets.sync",
    "templates.manage",
    "roles.assign",
}

# super_admin is the wildcard holder: "*" satisfies every has_permission check.
WILDCARD = "*"

ROLE_PERMISSIONS = {
    "member": frozenset(_MEMBER),
    "admin": frozenset(_ADMIN),
    "super_admin": frozenset({WILDCARD}),
}


def permissions_for(role):
    """Return the frozenset of permission strings granted to ``role``."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has_permission(role, perm):
    """True if ``role`` grants ``perm`` (wildcard-aware). Source of truth for
    :meth:`User.has_permission`."""
    perms = ROLE_PERMISSIONS.get(role, frozenset())
    return WILDCARD in perms or perm in perms
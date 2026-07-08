---
name: rbacmanager
description: Defines role-based access control (RBAC) rules for this application — roles (super_admin, admin, member), their permissions/restrictions, the authorization check order, the permission matrix, API guard pattern, JWT claim shape, and UI-hiding rules. Use this skill whenever adding or reviewing any endpoint, route, UI element, or feature that touches authorization — new API routes, permission checks, role assignment, admin-only features, ownership checks, or JWT claims. Also use when the user asks "who can do X", "should this be admin-only", "add a permission check", or invokes it directly as /rbacmanager.
---

# RBAC Manager

Authorization rules for this application. Always use Role-Based Access Control (RBAC). Never hardcode permissions — check role/permission, don't special-case a user or id.

## Roles

### super_admin — System Owner
**Permissions:** Full system access; manage tenants, organizations, users; assign roles; manage permissions; view audit logs; configure system; database maintenance; API key management.
**Restrictions:** None.

### admin — Organization Administrator
**Permissions:** Manage users in own organization; CRUD business data; approve workflows; view reports; configure organization settings.
**Restrictions:** Cannot create a Super Admin, access other organizations, modify system configuration, or delete audit logs.

### member — Standard User
**Permissions:** Login; view dashboard; create own records; edit own records; upload files; view assigned tasks.
**Restrictions:** Cannot access admin pages, manage users, change permissions, or view audit logs.

## Authorization check order

Every request must check, in this order:

```
Authentication → Organization → Role → Permission → Resource Ownership → Action
```

Short-circuit on the first failure — don't run later checks (e.g. ownership) before confirming authentication and role/permission.

## Permission matrix

| Resource | super_admin | admin | member |
|-----------|------------|--------|--------|
| Users | CRUD | CRUD (Org Only) | Read Self |
| Roles | CRUD | Read | None |
| Leave | CRUD | Approve | Create/Edit Own |
| Dashboard | All | Org | Personal |
| Audit Log | Read | Read Org | None |

## API guard pattern

Every protected endpoint requires, in order: **Current User → Role Check → Permission Check → Ownership Check → Execute**.

Example:
- `GET /users` requires `users.read`
- `POST /users` requires `users.create`
- `DELETE /users/{id}` requires `users.delete`

## UI rules

Hide UI elements based on permissions, but never rely on frontend hiding alone — backend authorization is mandatory on every request regardless of what the UI shows.

## JWT claims shape

```json
{
  "sub": "...",
  "org_id": "...",
  "role": "admin",
  "permissions": ["users.read", "leave.approve"]
}
```

## Best practice: permission checks over role checks

Prefer permission-based access over role-based checks so access can be tuned per-permission without new roles.

Avoid:
```
if user.role == "admin"
```

Prefer:
```
if user.has_permission("users.create")
```

Roles should only be collections of permissions — the code checks the permission, not the role name.

## Applying this to Project-Tracking

This project now implements all **three** roles (`super_admin`, `admin`, `member`) and permission strings — see `CLAUDE.md` → *Authorization model*. When adding or reviewing authorization here, follow the code that exists rather than re-deriving it:

### What's implemented (use these — don't reinvent)
- **Roles:** `backend/app/models.py:ROLES = ["super_admin", "admin", "member"]`. `ELEVATED_ROLES = ("super_admin", "admin")` marks the roles that pass owner-or-elevated scope checks.
- **Permission catalog:** `backend/app/permissions.py` — `ROLE_PERMISSIONS` (`member` ⊂ `admin`; `super_admin` = `{"*"}` wildcard). Plain data, no `models` import.
- **Two orthogonal axes — keep them separate:**
  - **Capability** ("may this role do X at all?") → permission strings, checked via `User.has_permission(perm)` and the `require_permission(user, perm)` helper in `backend/app/api/helpers.py`.
  - **Scope** ("own row vs any row?") → `require_owner_or_admin(user, owner_id)` (still the right tool). This is why `member` holds `projects.update` — capability granted, ownership narrows scope.
- **Live-role resolution:** `has_permission` reads the **live DB role at request time**, never a JWT claim, so role changes take effect immediately.
- **Role assignment:** `PATCH /api/users/:id/role` (`backend/app/api/users.py`), gated `roles.assign`. Guardrails: only a `super_admin` may grant/touch `super_admin`; nobody may change their own role.
- **Frontend:** `auth.hasPermission(perm)` / `auth.isSuperAdmin` (`frontend/src/stores/auth.js`); `/users` route + `UsersView.vue` are hidden/guarded on `roles.assign`.

### Guidance for new work
- Gate a **capability** with `require_permission(user, "<resource>.<action>")`; add the string to `ROLE_PERMISSIONS` in `permissions.py`. Gate **row scope** with `require_owner_or_admin`. Do **not** hardcode `role == "admin"` — use `has_permission` or `ELEVATED_ROLES`.
- Apply the check order (Authentication → Role/Permission → Ownership → Action) and the UI rule (hide in frontend, but the backend check is authoritative).

### Divergences from the generic matrix above (intentional — flag, don't "fix" silently)
- **No org/tenant scoping.** There is no `org_id` on users/resources and no `Organization` step in the check order. The JWT carries only `{role, name}` (no `org_id`, no `permissions` array — permissions are derived server-side from the live role; `to_dict()` exposes them only as advisory UI-hiding data). Treat the "Organization" check and JWT `org_id` as *not yet built*.
- **No audit log** and **no Leave resource** — those matrix rows are aspirational targets, not implemented.
- **Admin may demote a peer `admin` to `member`** (only the `super_admin` role is shielded). Consistent with "admin: Users CRUD (org only)", but confirm with the user before tightening.
- **Bootstrap:** first registered user is `admin` (not `super_admin`); `super_admin` is reachable only via `seed.py`, a direct DB edit, or promotion by an existing super_admin. There is deliberately no self-service path to the top role.

If asked to build org scoping or the audit log, use the full matrix + JWT shape above as the target and treat it as a superset of what's implemented today.

"""super_admin role + granular permission strings.

The `auth` fixture is the first registered user, so it is `admin`. Additional
users registered afterwards are `member`. A `super_admin` is minted by flipping
a member's role directly in the DB (mirrors the seed/DB bootstrap path).
"""
from app.extensions import Session
from app.models import User
from app.permissions import PAGE_KEYS, permissions_for, role_has_permission


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _make_super(email):
    """Promote an existing user to super_admin at the DB layer."""
    u = Session.query(User).filter_by(email=email).first()
    u.role = "super_admin"
    Session.commit()


# --- permission catalog ----------------------------------------------------

def test_role_permission_mapping():
    assert role_has_permission("super_admin", "anything.at.all")  # wildcard
    assert role_has_permission("admin", "roles.assign")
    assert role_has_permission("admin", "templates.manage")
    assert role_has_permission("admin", "sheets.sync")
    assert not role_has_permission("member", "roles.assign")
    assert not role_has_permission("member", "sheets.sync")
    # member keeps capability-level CRUD (scope is narrowed elsewhere)
    assert role_has_permission("member", "projects.update")
    assert "*" in permissions_for("super_admin")


def test_me_exposes_permissions(client, auth):
    res = client.get("/api/auth/me", headers=auth)
    perms = res.get_json()["user"]["permissions"]
    assert "roles.assign" in perms          # admin fixture
    assert "sheets.sync" in perms


def test_member_permissions_are_limited(client, auth):
    _member, _ = _register(client, "m@x.com")
    res = client.get("/api/auth/me", headers=_member)
    perms = res.get_json()["user"]["permissions"]
    assert "roles.assign" not in perms
    assert "projects.create" in perms


# --- role assignment endpoint ---------------------------------------------

def test_member_cannot_assign_roles(client, auth):
    member, mid = _register(client, "m@x.com")
    res = client.patch(f"/api/users/{mid}/role", json={"role": "admin"}, headers=member)
    assert res.status_code == 403


def test_admin_can_promote_member_to_admin(client, auth):
    _member, mid = _register(client, "m@x.com")
    res = client.patch(f"/api/users/{mid}/role", json={"role": "admin"}, headers=auth)
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["role"] == "admin"


def test_admin_cannot_grant_super_admin(client, auth):
    _member, mid = _register(client, "m@x.com")
    res = client.patch(
        f"/api/users/{mid}/role", json={"role": "super_admin"}, headers=auth
    )
    assert res.status_code == 403


def test_admin_cannot_modify_a_super_admin(client, auth):
    _member, mid = _register(client, "boss@x.com")
    _make_super("boss@x.com")
    res = client.patch(f"/api/users/{mid}/role", json={"role": "member"}, headers=auth)
    assert res.status_code == 403


def test_super_admin_can_grant_super_admin(client, auth):
    # promote the admin fixture user to super_admin, then have it grant super_admin
    _make_super("tester@x.com")
    _member, mid = _register(client, "m@x.com")
    res = client.patch(
        f"/api/users/{mid}/role", json={"role": "super_admin"}, headers=auth
    )
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["role"] == "super_admin"


def test_cannot_change_own_role(client, auth):
    me = client.get("/api/auth/me", headers=auth).get_json()["user"]
    res = client.patch(
        f"/api/users/{me['id']}/role", json={"role": "member"}, headers=auth
    )
    assert res.status_code == 403


def test_invalid_role_rejected(client, auth):
    _member, mid = _register(client, "m@x.com")
    res = client.patch(f"/api/users/{mid}/role", json={"role": "wizard"}, headers=auth)
    assert res.status_code == 422


# --- refactored guards still enforce --------------------------------------

def test_templates_manage_gate(client, auth):
    member, _ = _register(client, "m@x.com")
    # member lacks templates.manage
    denied = client.post("/api/ptemplate", json={"task": "T", "processId": 1}, headers=member)
    assert denied.status_code == 403
    # admin holds it
    ok = client.post("/api/ptemplate", json={"task": "T", "processId": 1}, headers=auth)
    assert ok.status_code == 201, ok.get_json()


# --- per-user page access ---------------------------------------------------

def test_page_permission_catalog():
    assert role_has_permission("member", "page.overview")
    assert role_has_permission("admin", "pages.assign")
    assert not role_has_permission("member", "pages.assign")


def test_default_member_has_all_pages(client, auth):
    member, _ = _register(client, "m@x.com")
    res = client.get("/api/auth/me", headers=member)
    body = res.get_json()["user"]
    assert set(body["pageAccess"]) == set(PAGE_KEYS)
    assert all(f"page.{k}" in body["permissions"] for k in PAGE_KEYS)


def test_admin_can_restrict_member_pages(client, auth):
    _member, mid = _register(client, "m@x.com")
    res = client.patch(
        f"/api/users/{mid}/pages", json={"pages": ["overview", "table"]}, headers=auth
    )
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["pageAccess"] == ["overview", "table"]
    assert "page.overview" in body["permissions"]
    assert "page.pipeline" not in body["permissions"]


def test_me_reflects_restricted_pages(client, auth):
    member, mid = _register(client, "m@x.com")
    client.patch(f"/api/users/{mid}/pages", json={"pages": ["overview"]}, headers=auth)
    res = client.get("/api/auth/me", headers=member)
    assert res.get_json()["user"]["pageAccess"] == ["overview"]


def test_member_cannot_assign_pages(client, auth):
    member, _ = _register(client, "m@x.com")
    other, oid = _register(client, "o@x.com")
    res = client.patch(f"/api/users/{oid}/pages", json={"pages": ["overview"]}, headers=member)
    assert res.status_code == 403


def test_cannot_set_pages_for_elevated_target(client, auth):
    _member, mid = _register(client, "boss@x.com")
    _make_super("boss@x.com")
    res = client.patch(f"/api/users/{mid}/pages", json={"pages": ["overview"]}, headers=auth)
    assert res.status_code == 403

    me = client.get("/api/auth/me", headers=auth).get_json()["user"]
    res_self = client.patch(
        f"/api/users/{me['id']}/pages", json={"pages": ["overview"]}, headers=auth
    )
    assert res_self.status_code == 403


def test_super_admin_can_set_member_pages(client, auth):
    _make_super("tester@x.com")
    _member, mid = _register(client, "m@x.com")
    res = client.patch(
        f"/api/users/{mid}/pages", json={"pages": ["overview"]}, headers=auth
    )
    assert res.status_code == 200, res.get_json()


def test_page_access_validation(client, auth):
    _member, mid = _register(client, "m@x.com")

    unknown = client.patch(f"/api/users/{mid}/pages", json={"pages": ["nope"]}, headers=auth)
    assert unknown.status_code == 422

    empty = client.patch(f"/api/users/{mid}/pages", json={"pages": []}, headers=auth)
    assert empty.status_code == 422

    not_list = client.patch(f"/api/users/{mid}/pages", json={"pages": "overview"}, headers=auth)
    assert not_list.status_code == 422


def test_full_page_set_normalizes_to_null(client, auth):
    _member, mid = _register(client, "m@x.com")
    res = client.patch(
        f"/api/users/{mid}/pages", json={"pages": list(PAGE_KEYS)}, headers=auth
    )
    assert res.status_code == 200
    assert res.get_json()["pageAccess"] == list(PAGE_KEYS)

    target = Session.get(User, mid)
    assert target.page_access is None


def test_promotion_clears_page_override(client, auth):
    _member, mid = _register(client, "m@x.com")
    client.patch(f"/api/users/{mid}/pages", json={"pages": ["overview"]}, headers=auth)

    client.patch(f"/api/users/{mid}/role", json={"role": "admin"}, headers=auth)
    target = Session.get(User, mid)
    assert target.page_access is None

    client.patch(f"/api/users/{mid}/role", json={"role": "member"}, headers=auth)
    target = Session.get(User, mid)
    assert set(target.allowed_pages) == set(PAGE_KEYS)
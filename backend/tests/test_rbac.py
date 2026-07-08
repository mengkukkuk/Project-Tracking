"""super_admin role + granular permission strings.

The `auth` fixture is the first registered user, so it is `admin`. Additional
users registered afterwards are `member`. A `super_admin` is minted by flipping
a member's role directly in the DB (mirrors the seed/DB bootstrap path).
"""
from app.extensions import Session
from app.models import User
from app.permissions import permissions_for, role_has_permission


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
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True


def test_register_first_user_is_admin(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "Boss", "email": "boss@x.com", "password": "secret123"},
    )
    assert res.status_code == 201
    assert res.get_json()["user"]["role"] == "admin"


def test_register_duplicate_email_rejected(client):
    payload = {"name": "A", "email": "dup@x.com", "password": "secret123"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 422
    assert "email" in res.get_json()["error"]["fields"]


def test_register_short_password_rejected(client):
    res = client.post(
        "/api/auth/register",
        json={"name": "A", "email": "a@x.com", "password": "123"},
    )
    assert res.status_code == 422


def test_login_and_me(client):
    client.post(
        "/api/auth/register",
        json={"name": "A", "email": "a@x.com", "password": "secret123"},
    )
    res = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert res.status_code == 200
    token = res.get_json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.get_json()["user"]["email"] == "a@x.com"


def test_login_bad_password(client):
    client.post(
        "/api/auth/register",
        json={"name": "A", "email": "a@x.com", "password": "secret123"},
    )
    res = client.post("/api/auth/login", json={"email": "a@x.com", "password": "wrong"})
    assert res.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/projects").status_code == 401

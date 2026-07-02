def _create(client, auth, **over):
    payload = {
        "name": "Test Project",
        "domain": "IoT",
        "customer": "ACME",
        "priority": "high",
        "value": 1_000_000,
        "progress": 20,
        "fiscalYear": "70",
        "tags": ["alpha", "beta"],
    }
    payload.update(over)
    return client.post("/api/projects", json=payload, headers=auth)


def test_create_project(client, auth):
    res = _create(client, auth)
    assert res.status_code == 201
    data = res.get_json()
    assert data["name"] == "Test Project"
    assert data["value"] == 1_000_000
    assert {t["name"] for t in data["tags"]} == {"alpha", "beta"}
    # creation is recorded in the activity feed
    assert any(a["action"] == "created" for a in data["activities"])


def test_create_validation_errors(client, auth):
    res = client.post("/api/projects", json={"value": -5}, headers=auth)
    assert res.status_code == 422
    fields = res.get_json()["error"]["fields"]
    assert "name" in fields  # required

    # status is no longer user-settable — bogus values are silently ignored
    # rather than 422'd, since the server derives status from progress.
    res = _create(client, auth, status="Nonsense")
    assert res.status_code == 201

    res = _create(client, auth, progress=999)
    # progress is clamped at the validator boundary -> rejected as > maximum
    assert res.status_code == 422


def test_list_filter_search_sort(client, auth):
    # Status is derived from progress now (0-19 Pre-Sale, ..., 80-100 Completed),
    # so seed projects with the right progress % to land them in each stage.
    _create(client, auth, name="Alpha", progress=10, value=100)    # -> Pre-Sale
    _create(client, auth, name="Bravo", progress=90, value=300)    # -> Completed
    _create(client, auth, name="Charlie", progress=95, value=200)  # -> Completed

    res = client.get("/api/projects?status=Completed", headers=auth)
    assert res.status_code == 200
    body = res.get_json()
    assert body["total"] == 2
    assert all(p["status"] == "Completed" for p in body["items"])

    res = client.get("/api/projects?q=brav", headers=auth)
    assert res.get_json()["total"] == 1

    res = client.get("/api/projects?sort=value&dir=asc", headers=auth)
    values = [p["value"] for p in res.get_json()["items"]]
    assert values == sorted(values)


def test_get_update_delete(client, auth):
    pid = _create(client, auth).get_json()["id"]

    res = client.get(f"/api/projects/{pid}", headers=auth)
    assert res.status_code == 200

    # status is no longer accepted in PATCH bodies — it derives from progress.
    # progress=50 -> "award" bucket (40-59). No "moved" activity is logged
    # because status is computed, not assigned.
    res = client.patch(
        f"/api/projects/{pid}", json={"status": "award", "progress": 50}, headers=auth
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "award"
    assert data["progress"] == 50

    assert client.delete(f"/api/projects/{pid}", headers=auth).status_code == 204
    assert client.get(f"/api/projects/{pid}", headers=auth).status_code == 404


def test_pagination(client, auth):
    for i in range(5):
        _create(client, auth, name=f"P{i}")
    res = client.get("/api/projects?perPage=2&page=1", headers=auth)
    body = res.get_json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_create_team_size_complexity(client, auth):
    res = _create(client, auth, teamSize=6, complexity=7)
    assert res.status_code == 201
    data = res.get_json()
    assert data["teamSize"] == 6
    assert data["complexity"] == 7


def test_team_size_complexity_default_none(client, auth):
    res = _create(client, auth)
    assert res.status_code == 201
    data = res.get_json()
    assert data["teamSize"] is None
    assert data["complexity"] is None


def test_update_team_size_complexity(client, auth):
    pid = _create(client, auth).get_json()["id"]

    res = client.patch(
        f"/api/projects/{pid}", json={"teamSize": 4, "complexity": 9}, headers=auth
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["teamSize"] == 4
    assert data["complexity"] == 9

    # out-of-range values are rejected
    res = client.patch(f"/api/projects/{pid}", json={"complexity": 11}, headers=auth)
    assert res.status_code == 422
    res = client.patch(f"/api/projects/{pid}", json={"teamSize": 0}, headers=auth)
    assert res.status_code == 422

    # explicit null clears the field back to unset
    res = client.patch(
        f"/api/projects/{pid}", json={"teamSize": None, "complexity": None}, headers=auth
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["teamSize"] is None
    assert data["complexity"] is None

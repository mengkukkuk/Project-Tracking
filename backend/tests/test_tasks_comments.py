def _project(client, auth):
    return client.post(
        "/api/projects",
        json={"name": "Host", "status": "Pre-Sale"},
        headers=auth,
    ).get_json()["id"]


def test_task_lifecycle(client, auth):
    pid = _project(client, auth)

    res = client.post(
        f"/api/projects/{pid}/tasks",
        json={"title": "Do the thing", "assignee": "นายเอ"},
        headers=auth,
    )
    assert res.status_code == 201
    tid = res.get_json()["id"]
    assert res.get_json()["done"] is False

    res = client.patch(f"/api/tasks/{tid}", json={"done": True}, headers=auth)
    assert res.get_json()["done"] is True

    # task should appear in the project detail payload
    detail = client.get(f"/api/projects/{pid}", headers=auth).get_json()
    assert detail["taskCount"] == 1
    assert detail["taskDone"] == 1

    assert client.delete(f"/api/tasks/{tid}", headers=auth).status_code == 204


def test_comment_lifecycle(client, auth):
    pid = _project(client, auth)
    res = client.post(
        f"/api/projects/{pid}/comments", json={"body": "Looks good"}, headers=auth
    )
    assert res.status_code == 201
    cid = res.get_json()["id"]
    assert res.get_json()["user"]["email"] == "tester@x.com"

    assert client.delete(f"/api/comments/{cid}", headers=auth).status_code == 204


def test_task_requires_title(client, auth):
    pid = _project(client, auth)
    res = client.post(f"/api/projects/{pid}/tasks", json={}, headers=auth)
    assert res.status_code == 422

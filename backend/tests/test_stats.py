from datetime import date, timedelta


def test_stats_aggregation(client, auth):
    overdue_due = (date.today() - timedelta(days=3)).isoformat()
    client.post(
        "/api/projects",
        json={"name": "A", "status": "Pre-Sale", "value": 100, "domain": "IoT",
              "priority": "high", "dueDate": overdue_due},
        headers=auth,
    )
    client.post(
        "/api/projects",
        json={"name": "B", "status": "Completed", "value": 300, "domain": "PLC",
              "progress": 100},
        headers=auth,
    )

    res = client.get("/api/stats", headers=auth)
    assert res.status_code == 200
    s = res.get_json()
    assert s["totalProjects"] == 2
    assert s["totalValue"] == 400
    assert s["pipelineValue"] == 100  # excludes Completed
    assert s["completed"] == 1
    assert s["overdue"] == 1
    assert s["byDomain"]["IoT"] == 1
    assert s["byPriority"]["high"] == 1
    assert len(s["funnel"]) == 5

"""GET /api/lookups — read-only lookup_type/lookup_value taxonomy."""
from app.extensions import Session
from app.models import LookupType, LookupValue


def test_lookups_nested_active_only_ordered(client, auth):
    sensor = LookupType(code="SENSOR", name="Sensor", description="Sensor")
    inactive_type = LookupType(
        code="OLD", name="Old", description="Old", is_active=False
    )
    Session.add_all([sensor, inactive_type])
    Session.flush()

    Session.add_all([
        LookupValue(
            lookup_type_id=sensor.id, code="TEMP", display_name="Temp sensor"
        ),
        LookupValue(
            lookup_type_id=sensor.id, code="DIFFUSE", display_name="Diffuse sensor"
        ),
        LookupValue(
            lookup_type_id=sensor.id,
            code="OLD_VAL",
            display_name="Old value",
            is_active=False,
        ),
    ])
    Session.commit()

    res = client.get("/api/lookups", headers=auth)
    assert res.status_code == 200, res.get_json()
    types = res.get_json()["types"]

    # Inactive type excluded entirely.
    codes = [t["code"] for t in types]
    assert "OLD" not in codes
    assert "SENSOR" in codes

    sensor_out = next(t for t in types if t["code"] == "SENSOR")
    assert sensor_out["description"] == "Sensor"
    value_names = [v["displayName"] for v in sensor_out["values"]]
    # Inactive value excluded; remaining ordered by display_name asc.
    assert value_names == ["Diffuse sensor", "Temp sensor"]


def test_lookups_requires_auth(client):
    res = client.get("/api/lookups")
    assert res.status_code == 401

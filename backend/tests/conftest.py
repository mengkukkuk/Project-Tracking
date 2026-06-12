"""Shared pytest fixtures: a fresh in-memory app + authenticated client."""
import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import Session
from app.models import Base


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    yield app
    # Tear the schema down between tests so each gets a clean slate.
    from app.extensions import engine

    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(client):
    """Register a user and return an Authorization header dict."""
    res = client.post(
        "/api/auth/register",
        json={"name": "Tester", "email": "tester@x.com", "password": "secret123"},
    )
    assert res.status_code == 201, res.get_json()
    token = res.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}

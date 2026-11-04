import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.store import Store
from app.api import create_app
from app.services import load_catalog, seed_people
from app.models import DirectoryUser
from app.security import COOKIE


@pytest.fixture
def store(tmp_path):
    s = Store(Settings(tmp_path, f"sqlite:///{tmp_path/'control.db'}"))
    load_catalog(s)
    seed_people(s)
    return s


@pytest.fixture
def client(store):
    app = create_app(store=store)
    with store.cs() as s:
        s.add(
            DirectoryUser(
                id="test-hr",
                username="test-hr",
                display_name="Test HR",
                roles=["hr"],
                groups=[],
                source="local",
            )
        )
    token, actor = app.state.auth.create_session("test-hr")
    with TestClient(app) as c:
        c.cookies.set(COOKIE, token)
        c.headers["X-CSRF-Token"] = actor.csrf_token
        yield c

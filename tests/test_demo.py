"""Presentation accounts remain regular scoped sessions in an isolated demo store."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import create_app
from app.config import Settings
from app.demo import prepare_demo, demo_credentials
from app.models import Campaign, DirectoryUser, Participant
from app.security import AuthService, actor_for_user
from app.store import Store, DomainError


@pytest.fixture
def demo_store(tmp_path):
    store = Store(
        Settings(
            tmp_path, f"sqlite:///{tmp_path / 'control.db'}", presentation_demo=True
        )
    )
    prepare_demo(store)
    return store


@pytest.mark.parametrize("mode", ["demo", "production", "development"])
def test_mode_selects_separate_storage(monkeypatch, tmp_path, mode):
    monkeypatch.setenv("APP_MODE", mode)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CONTROL_STORE_URL", raising=False)
    settings = Settings.from_env()
    assert settings.presentation_demo == (mode == "demo")
    assert settings.demo == (mode != "production")
    assert settings.data_dir == (
        tmp_path / "presentation-demo" if mode == "demo" else tmp_path
    )
    assert settings.control_url == f"sqlite:///{settings.data_dir / 'control.db'}"


def test_demo_ignores_external_control_store(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("CONTROL_STORE_URL", "postgresql://must-not-connect/private")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    settings = Settings.from_env()
    assert (
        settings.control_url
        == f"sqlite:///{tmp_path / 'presentation-demo' / 'control.db'}"
    )


def test_demo_does_not_inherit_production_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_MODE", "demo")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CONTROL_STORE_URL", raising=False)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "must-not-use-production-key")
    assert Settings.from_env().secret_key is None


def test_presentation_logins_use_real_scope_and_permissions(demo_store):
    accounts = demo_credentials(demo_store)
    assert len(set(accounts.values())) == 4
    with TestClient(create_app(store=demo_store)) as client:
        for username, role, count in [
            ("hr", "hr", 30),
            ("employee", "employee", 1),
            ("admin", "admin", 0),
            ("manager", "manager", 10),
        ]:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "username": username,
                    "password": accounts[username],
                },
            )
            assert response.status_code == 200
            actor = response.json()
            assert actor["roles"] == [role]
            assert actor["temporary_password"] is False
            client.headers["X-CSRF-Token"] = actor["csrf_token"]
            boot = client.get("/api/v1/bootstrap").json()
            assert len(boot["participants"]) == count
            assert len(boot["campaigns"]) == (0 if role == "admin" else 2)
            if role in ("employee", "manager"):
                assert all(p["team_id"] == "team-data" for p in boot["participants"])
                assert client.get("/api/v1/admin/connections/llm").status_code == 403
            if role == "admin":
                assert client.get("/api/v1/catalog").status_code == 403
                assert client.get("/api/v1/admin/connections/llm").status_code == 200
            assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/bootstrap").status_code == 401
    with demo_store.cs() as s:
        users = list(s.scalars(select(DirectoryUser)))
        assert len(users) == 32
        assert all(user.source == "demo" for user in users)
        for user in users:
            if user.username in accounts:
                assert user.password_hash.startswith("$argon2")
                assert user.password_hash != accounts[user.username]
            else:
                assert user.password_hash is None


def test_demo_bootstrap_is_repeatable_without_resetting_presentation(demo_store):
    before = demo_credentials(demo_store)
    with demo_store.session() as s:
        s.get(Participant, "team-data-person-02").name = "Presentation edit"
    prepare_demo(demo_store)
    assert demo_credentials(demo_store) == before
    with demo_store.session() as s:
        assert len(list(s.scalars(select(Campaign)))) == 2
        assert s.get(Participant, "team-data-person-02").name == "Presentation edit"


def test_demo_does_not_allow_wrong_password_or_unprovisioned_login(demo_store):
    auth = AuthService(demo_store)
    for name in ["hr", "employee", "admin", "manager", "person.team-data-person-03"]:
        with pytest.raises(DomainError) as error:
            auth.login(name, "wrong-password", "127.0.0.1")
        assert error.value.status == 401


def test_copied_demo_database_and_sessions_are_rejected_outside_demo(demo_store):
    auth = AuthService(demo_store)
    token, actor = auth.login("hr", demo_credentials(demo_store)["hr"], "127.0.0.1")
    demo_store.settings.presentation_demo = False
    for mode in [True, False]:
        demo_store.settings.demo = mode
        with pytest.raises(RuntimeError, match="Demo kimlik deposu"):
            AuthService(demo_store)
        with pytest.raises(DomainError):
            auth.actor(token)
        with pytest.raises(DomainError):
            actor_for_user(demo_store, actor.id)
        with pytest.raises(RuntimeError):
            demo_credentials(demo_store)


def test_credentials_are_not_served_by_web_or_api(demo_store):
    accounts = demo_credentials(demo_store)
    with TestClient(create_app(store=demo_store)) as client:
        for url in [
            "/demo-access.json",
            "/api/v1/demo-accounts",
            "/data/demo-access.json",
        ]:
            response = client.get(url)
            assert all(secret not in response.text for secret in accounts.values())


def test_worker_and_store_reject_demo_data_in_production(demo_store):
    path = demo_store.settings.data_dir
    with pytest.raises(RuntimeError, match="Demo kimlik deposu"):
        Store(
            Settings(
                path,
                f"sqlite:///{path / 'control.db'}",
                demo=False,
                secret_key=(path / ".encryption-key").read_text(),
            )
        )


def test_demo_requires_explicit_bootstrap(tmp_path):
    store = Store(
        Settings(
            tmp_path, f"sqlite:///{tmp_path / 'control.db'}", presentation_demo=True
        )
    )
    with pytest.raises(RuntimeError, match="bootstrap"):
        AuthService(store)
    with pytest.raises(RuntimeError):
        Settings(
            tmp_path,
            f"sqlite:///{tmp_path / 'control.db'}",
            demo=False,
            presentation_demo=True,
        )

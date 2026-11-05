"""First production accounts and the operator-supplied PostgreSQL binding."""

import socket
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import URL

from app.api import create_app
from app.config import Settings
from app.models import DirectoryUser, ProfileVersion, Binding
from app.security import AuthService
from app.store import Store, DomainError

ADMIN_PASSWORD = "Fixture-integration-47!"
HR_PASSWORD = "Fixture-people-58!"
DATABASE_URL = (
    "postgresql+psycopg://app:fixture-password@db.example/aptilume"
    "?sslmode=verify-full&sslrootcert=/etc/certs/postgres-ca.crt"
)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("BOOTSTRAP_HR_PASSWORD", HR_PASSWORD)
    store = Store(
        Settings(
            tmp_path,
            f"sqlite:///{tmp_path / 'control.db'}",
            Fernet.generate_key().decode(),
            demo=False,
            public_base_url="https://portal.example",
        )
    )
    return store, AuthService(store)


def test_local_hr_and_admin_login_without_ad_with_separate_scope(installed):
    store, auth = installed
    with TestClient(
        create_app(store=store, auth_service=auth), base_url="https://portal.example"
    ) as client:
        for username, password, role in [
            ("hr", HR_PASSWORD, "hr"),
            ("admin", ADMIN_PASSWORD, "admin"),
        ]:
            login = client.post(
                "/api/v1/auth/login", json={"username": username, "password": password}
            )
            assert login.status_code == 200
            assert login.json()["roles"] == [role]
            assert login.json()["can_change_password"]
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            assert client.get("/api/v1/admin/connections/db").status_code == 200
            assert client.get("/api/v1/skills").status_code == (
                200 if role == "hr" else 403
            )
            assert client.get("/api/v1/prompt-policies").status_code == (
                200 if role == "hr" else 403
            )
            assert client.post("/api/v1/auth/logout").status_code == 200
    with store.cs() as session:
        users = list(session.scalars(select(DirectoryUser)))
        assert {u.username for u in users} == {"admin", "hr"}
        assert all(
            u.source == "local" and u.password_hash.startswith("$argon2") for u in users
        )
        assert all(not u.temporary_password for u in users)


def test_local_hr_password_rotation_revokes_only_hr_sessions(installed):
    store, auth = installed
    admin_token, _ = auth.login("admin", ADMIN_PASSWORD, "fixture-admin")
    hr_token, hr = auth.login("hr", HR_PASSWORD, "fixture-hr")
    with pytest.raises(DomainError):
        auth.change_password(hr, "wrong", "Fixture-rotated-91!")
    auth.change_password(hr, HR_PASSWORD, "Fixture-rotated-91!")
    with pytest.raises(DomainError):
        auth.actor(hr_token)
    assert auth.actor(admin_token).roles == {"admin"}
    assert auth.login("HR", "Fixture-rotated-91!", "fixture-new")[1].roles == {"hr"}
    with pytest.raises(DomainError) as err:
        auth.login("hr", HR_PASSWORD, "fixture-old")
    assert err.value.status == 401


def test_rebootstrap_never_resets_password_roles_or_reactivates_hr(
    installed, monkeypatch
):
    store, auth = installed
    with store.cs() as session:
        initial_hash = session.get(DirectoryUser, "local-hr").password_hash
    monkeypatch.setenv("BOOTSTRAP_HR_PASSWORD", "Fixture-different-29!")
    AuthService(store)
    with store.cs() as session:
        hr = session.get(DirectoryUser, "local-hr")
        assert hr.password_hash == initial_hash
        hr.active = False
    AuthService(store)
    with pytest.raises(DomainError) as err:
        auth.login("hr", HR_PASSWORD, "fixture-inactive")
    assert err.value.status == 401


@pytest.mark.parametrize("password", ["", "hr", "admin123456789012345"])
def test_invalid_hr_bootstrap_rolls_back_account_creation(
    tmp_path, monkeypatch, password
):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("BOOTSTRAP_HR_PASSWORD", password)
    store = Store(Settings(tmp_path, f"sqlite:///{tmp_path / 'control.db'}"))
    with pytest.raises(RuntimeError, match="BOOTSTRAP_HR_PASSWORD"):
        AuthService(store)
    with store.cs() as session:
        assert not list(session.scalars(select(DirectoryUser)))


def test_database_url_selects_both_stores_but_demo_ignores_it(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("CONTROL_STORE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("APP_MODE", "production")
    settings = Settings.from_env()
    assert settings.control_url == settings.application_url == DATABASE_URL
    monkeypatch.setenv("APP_MODE", "demo")
    settings = Settings.from_env()
    assert settings.application_url is None
    assert settings.control_url.startswith("sqlite:")


def test_initial_postgres_binding_encrypts_secret_and_preserves_existing_binding(
    tmp_path, monkeypatch
):
    # Transport is covered by the PostgreSQL fixture; inspect the persisted binding here.
    monkeypatch.setattr(Store, "engine", property(lambda s: s.control))
    settings = Settings(
        tmp_path,
        f"sqlite:///{tmp_path / 'control.db'}",
        Fernet.generate_key().decode(),
        demo=False,
        allowed_db_hosts="db.example",
        application_url=DATABASE_URL,
    )
    store = Store(settings)
    with store.cs() as session:
        binding = session.get(Binding, "application_db")
        version = session.get(ProfileVersion, binding.version_id)
        version_id = version.id
        assert version.config["engine"] == "postgresql"
        assert version.config["host"] == "db.example"
        assert version.config["sslrootcert"] == "/etc/certs/postgres-ca.crt"
        assert "fixture-password" not in str(version.config)
        assert version.secret != "fixture-password"
        assert store.decrypt(version.secret) == "fixture-password"
    # Changed initial settings must not silently move an existing application store.
    settings.application_url = DATABASE_URL.replace("db.example", "other.example")
    restored = Store(settings)
    with restored.cs() as session:
        assert session.get(Binding, "application_db").version_id == version_id
    assert not (tmp_path / "application.db").exists()


def test_bootstrap_database_does_not_bypass_production_tls(tmp_path, monkeypatch):
    monkeypatch.setattr(Store, "engine", property(lambda s: s.control))
    with pytest.raises(DomainError) as err:
        Store(
            Settings(
                tmp_path,
                f"sqlite:///{tmp_path / 'control.db'}",
                Fernet.generate_key().decode(),
                demo=False,
                allowed_db_hosts="db.example",
                application_url=DATABASE_URL.replace("verify-full", "disable"),
            )
        )
    assert err.value.code == "database_tls_required"


def test_secret_url_authorizes_only_its_exact_target_and_still_blocks_metadata(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(Store, "engine", property(lambda s: s.control))
    store = Store(
        Settings(
            tmp_path,
            f"sqlite:///{tmp_path / 'control.db'}",
            Fernet.generate_key().decode(),
            demo=False,
            application_url=DATABASE_URL,
        )
    )
    cfg, secret = store.bootstrap_db_config(DATABASE_URL)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.20.30.40", 5432))
        ],
    )
    url = store.db_url(cfg, secret, connect=True)
    assert (
        url.query["hostaddr"] == "10.20.30.40" and url.query["sslmode"] == "verify-full"
    )
    for changed in [{"host": "other.example"}, {"port": 5433}]:
        with pytest.raises(DomainError) as err:
            store.db_url({**cfg, **changed}, secret, connect=True)
        assert err.value.code == "host_not_allowed"
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 5432))
        ],
    )
    with pytest.raises(DomainError) as err:
        store.db_url(cfg, secret, connect=True)
    assert err.value.code == "blocked_endpoint"
    # Explicit operator restrictions remain authoritative over the convenience default.
    store.settings.allowed_db_hosts = "other.example"
    with pytest.raises(DomainError) as err:
        store.db_url(cfg, secret, connect=True)
    assert err.value.code == "host_not_allowed"


@pytest.mark.parametrize(
    "url",
    [
        "secret-without-a-url",
        "sqlite:///unexpected.db",
        "postgresql://app:secret@db.example/aptilume",
        "postgresql+psycopg://app:secret@db.example/aptilume?options=-c%20unsafe=1",
        "postgresql+psycopg://app:secret@db.example/aptilume?sslmode=require&sslmode=disable",
        "postgresql+psycopg://app:secret@db.example/aptilume?connect_timeout=nan",
    ],
)
def test_invalid_bootstrap_urls_are_rejected_without_echoing_secrets(url):
    with pytest.raises(DomainError) as err:
        Store.bootstrap_db_config(url)
    assert err.value.code == "invalid_database_url"
    assert "secret" not in str(err.value)


def test_bootstrap_url_preserves_encoded_password():
    url = URL.create(
        "postgresql+psycopg",
        username="app",
        password="p@ss:/?#%+!",
        host="db.example",
        database="aptilume",
        query={"sslmode": "verify-full"},
    )
    cfg, password = Store.bootstrap_db_config(url.render_as_string(hide_password=False))
    assert password == "p@ss:/?#%+!" and cfg["sslmode"] == "verify-full"

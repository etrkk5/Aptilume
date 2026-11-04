"""Regressions for the security review, using isolated data and synthetic endpoints."""

import copy
import hashlib
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import create_app
from app.config import Settings
from app.directory import (
    directory_config,
    save_directory_config,
    propose_directory_change,
    approve_directory_change,
)
from app.models import *
from app.network import resolve_target
from app.providers import Provider, validate_grade
from app.security import AuthService, COOKIE, cookie_name, strong_password
from app.store import Store, DomainError
from app.throttle import reserve
from app.worker import Worker
from app.retention import cleanup
from test_access import (
    scoped,
    open_campaign,
    publication,
    FakeDirectory,
    directory_rows,
    configure,
    P,
)
from app.services import seed_answers, campaign_transition, start_run


@pytest.mark.parametrize("mode", ["prodution", "prod", "DEVELOPMENT", "", "DEMO"])
def test_unknown_environment_never_relaxes_security(monkeypatch, mode):
    monkeypatch.setenv("APP_MODE", mode)
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_default_environment_is_production(monkeypatch):
    monkeypatch.delenv("APP_MODE", raising=False)
    assert not Settings.from_env().demo


@pytest.mark.parametrize(
    "origin",
    [
        "",
        "http://portal.example",
        "https://user:pass@portal.example",
        "https://portal.example/path",
        "https://portal.example?token=x",
    ],
)
def test_production_requires_fixed_https_origin(store, origin):
    store.settings.demo = False
    store.settings.public_base_url = origin
    with pytest.raises(RuntimeError):
        create_app(store=store)


def test_egress_dns_is_pinned_and_mapped_loopback_is_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                0,
                "",
                ("::ffff:127.0.0.1", 443, 0, 0),
            )
        ],
    )
    with pytest.raises(DomainError) as err:
        resolve_target("llm.example", 443, "llm.example", "127.0.0.0/8")
    assert err.value.code == "blocked_endpoint"


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "100.100.100.200",
        "168.63.129.16",
        "::",
        "::1",
        "ff02::1",
        "fd00:ec2::254",
    ],
)
def test_egress_metadata_and_special_addresses_blocked(monkeypatch, address):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443))],
    )
    with pytest.raises(DomainError):
        resolve_target("llm.example", 443, "llm.example", "0.0.0.0/0,::/0")


def test_private_egress_and_nonstandard_port_require_explicit_policy(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.20.30.40", 8443))
        ],
    )
    with pytest.raises(DomainError):
        resolve_target("llm.example", 8443, "llm.example", "10.0.0.0/8")
    with pytest.raises(DomainError):
        resolve_target("llm.example", 8443, "llm.example:8443")
    assert resolve_target("llm.example", 8443, "llm.example:8443", "10.20.30.0/24") == [
        "10.20.30.40"
    ]


def test_production_database_tls_and_hostaddr_pin(store, monkeypatch):
    store.settings.demo = False
    store.settings.allowed_db_hosts = "db.example"
    store.settings.allowed_cidrs = "10.0.0.0/8"
    cfg = {
        "engine": "postgresql",
        "host": "db.example",
        "database": "skills",
        "username": "app",
        "sslmode": "disable",
    }
    with pytest.raises(DomainError):
        store.db_url(cfg)
    cfg["sslmode"] = "verify-full"
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.20.30.40", 5432))
        ],
    )
    url = store.db_url(cfg, "fixture-only", connect=True)
    assert (
        url.host == "db.example"
        and url.query["hostaddr"] == "10.20.30.40"
        and url.query["sslmode"] == "verify-full"
    )
    with pytest.raises(DomainError):
        store.db_url({**cfg, "host": "other.example"})


def test_endpoint_change_cannot_reuse_a_secret(store):
    store.settings.allowed_hosts = "one.example,two.example"
    cfg = {
        "provider": "openai_compatible_chat",
        "model": "fixture",
        "endpoint": "https://one.example/v1",
    }
    p = store.save_profile("llm", "Fixture", cfg, "fixture-secret")
    with pytest.raises(DomainError) as err:
        store.save_profile(
            "llm",
            "Changed",
            {**cfg, "endpoint": "https://two.example/v1"},
            profile_id=p["id"],
        )
    assert err.value.code == "secret_reentry_required"
    assert store.resolve(version_id=p["id"] + ":1")["secret"] == "fixture-secret"
    new = store.save_profile(
        "llm",
        "Changed",
        {**cfg, "endpoint": "https://two.example/v1"},
        "new-fixture-secret",
        profile_id=p["id"],
    )
    assert new["version"] == 2


@pytest.mark.parametrize(
    "cfg",
    [
        {"secret": "plaintext"},
        {"timeout": 0},
        {"timeout": float("inf")},
        {"concurrency": "3"},
        {"headers": {"Authorization": "secret"}},
        {"model": []},
        {"endpoint": "https://user:secret@llm.example/v1"},
    ],
)
def test_connection_validation_rejects_unsafe_config_fields(store, cfg):
    store.settings.allowed_hosts = "llm.example"
    with pytest.raises(DomainError):
        store.save_profile(
            "llm",
            "Fixture",
            {
                "provider": "openai_compatible_chat",
                "model": "fixture",
                "endpoint": "https://llm.example/v1",
                **cfg,
            },
        )


def test_legacy_plaintext_config_is_not_disclosed(store, client):
    with store.cs() as s:
        p = Profile(
            id="legacy-bad",
            kind="llm",
            name="Legacy",
            config={
                "provider": "openai_compatible_chat",
                "model": "fixture",
                "secret": "legacy-private",
                "endpoint": "https://user:legacy-private@llm.example/v1?key=legacy-private",
            },
            version=1,
        )
        s.add(p)
    result = client.get("/api/v1/admin/connections/llm")
    assert "legacy-private" not in result.text and "user:" not in result.text


def test_account_throttle_survives_ip_rotation(store):
    auth = AuthService(store)
    for i in range(5):
        with pytest.raises(DomainError) as err:
            auth.login("admin", "wrong", f"198.51.100.{i}")
        assert err.value.status == 401
    with pytest.raises(DomainError) as err:
        auth.login("admin", "wrong", "203.0.113.99")
    assert err.value.status == 429


def test_rate_reservations_are_atomic_across_store_instances(store):
    second = Store(store.settings)

    def attempt(i):
        try:
            reserve(store if i % 2 else second, "race", "same-actor", 5, 3600)
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, range(20)))
    assert sum(results) == 5


def test_login_slots_bound_argon_work(store, monkeypatch):
    import app.security as security

    class Busy:
        def acquire(self, blocking=False):
            return False

    monkeypatch.setattr(security, "_login_slots", Busy())
    with pytest.raises(DomainError) as err:
        AuthService(store).login("admin", "admin", "test")
    assert err.value.status == 429


def test_repeated_ldap_login_does_not_rescan_directory(store):
    class Counting(FakeDirectory):
        calls = 0

        def snapshot(self):
            type(self).calls += 1
            return super().snapshot()

    Counting.rows = directory_rows()
    configure(store)
    auth = AuthService(store, Counting)
    auth.login("employee", "directory-password", "test")
    auth.login("employee", "directory-password", "test")
    assert Counting.calls == 1


def test_directory_proposal_does_not_change_authority_without_hr(store, scoped):
    app, as_user = scoped
    save_directory_config(
        store, {"role_groups": {"hr": ["cn=existing-hr"], "admin": [], "manager": []}}
    )
    with store.cs() as s:
        s.add(
            Setting(key="directory_initialized", value={"initialized_at": time.time()})
        )
    with as_user("ia") as c:
        result = c.put(
            "/api/v1/admin/directory",
            json={
                "role_groups": {"hr": ["cn=attacker-owned"], "admin": [], "manager": []}
            },
        )
        assert (
            result.status_code == 200 and result.json()["status"] == "pending_approval"
        )
        change = result.json()["change"]["id"]
        assert directory_config(store)["role_groups"]["hr"] == ["cn=existing-hr"]
        assert (
            c.post("/api/v1/admin/directory/changes/" + change + "/approve").status_code
            == 403
        )
        assert c.get("/api/v1/admin/directory").json()["approval_required"]
    with as_user("hr") as c:
        assert (
            c.post("/api/v1/admin/directory/changes/" + change + "/approve").status_code
            == 200
        )
        assert (
            c.post("/api/v1/admin/directory/changes/" + change + "/approve").status_code
            == 409
        )
    assert directory_config(store)["role_groups"]["hr"] == ["cn=attacker-owned"]
    # HR owns the trust policy; the integration admin's proposal alone was ineffective.


def test_superseded_directory_proposal_cannot_be_approved(store, scoped):
    _, as_user = scoped
    with store.cs() as s:
        s.add(Setting(key="directory_initialized", value={}))
    with as_user("ia") as c:
        first = c.put(
            "/api/v1/admin/directory", json={"include_descendants": False}
        ).json()["change"]["id"]
        second = c.put(
            "/api/v1/admin/directory", json={"include_descendants": True}
        ).json()["change"]["id"]
    with as_user("hr") as c:
        assert (
            c.post("/api/v1/admin/directory/changes/" + first + "/approve").status_code
            == 409
        )
        assert (
            c.post("/api/v1/admin/directory/changes/" + second + "/reject").status_code
            == 200
        )


def test_admin_cannot_activate_data_transfer_and_production_copy_is_offline(
    store, scoped
):
    _, as_user = scoped
    p = store.profiles("llm")[0]
    db = store.save_profile(
        "db",
        "Copy",
        {"engine": "sqlite", "path": str(store.settings.data_dir / "copy.db")},
    )
    with as_user("ia") as c:
        assert (
            c.put(
                "/api/v1/admin/service-bindings/evaluation",
                json={"profile_id": p["id"]},
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v1/admin/db-connections/" + db["id"] + "/activate",
                json={"copy_existing": True},
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v1/admin/db-connections/" + db["id"] + "/migration-preview"
            ).status_code
            == 403
        )
    store.settings.demo = False
    with pytest.raises(DomainError) as err:
        store.activate_db(db["id"])
    assert err.value.code == "offline_migration_required"


def test_reauthentication_required_for_old_privileged_session(store, scoped):
    app, _ = scoped
    token, actor = app.state.auth.create_session("hr")
    with store.cs() as s:
        s.get(AuthSession, hashlib.sha256(token.encode()).hexdigest()).expires_at = (
            time.time() + 28800 - 901
        )
    with TestClient(app) as c:
        c.cookies.set(COOKIE, token)
        c.headers["X-CSRF-Token"] = actor.csrf_token
        r = c.put(
            "/api/v1/admin/service-bindings/evaluation",
            json={"profile_id": store.profiles("llm")[0]["id"]},
        )
        assert r.status_code == 401 and r.json()["code"] == "reauthentication_required"


@pytest.mark.parametrize("chunked", [False, True])
def test_login_body_limit_catches_declared_and_streamed_sizes(store, chunked):
    app = create_app(store=store)
    with TestClient(app) as c:
        content = (x for x in [b"x" * 5000, b"x" * 5000]) if chunked else b"x" * 9000
        result = c.post(
            "/api/v1/auth/login",
            content=content,
            headers={"Content-Type": "application/json"},
        )
        assert result.status_code == 413
        assert result.headers["x-content-type-options"] == "nosniff"


def test_validation_never_echoes_password_and_unknown_fields(store, client):
    result = client.post(
        "/api/v1/auth/password",
        json={"current_password": "sensitive-current", "new_password": "secret"},
    )
    assert result.status_code == 422
    assert "sensitive-current" not in result.text and "secret" not in result.text
    assert (
        client.post(
            "/api/v1/teams", json={"name": [], "role": {}, "targets": None}
        ).status_code
        == 422
    )


def test_production_origin_cookie_and_error_envelope(store, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Fixture-Strong-Password-42")
    store.settings.demo = False
    store.settings.public_base_url = "https://portal.example"
    app = create_app(store=store)

    @app.get("/api/v1/crash-fixture")
    def crash():
        raise RuntimeError("private-connection-secret")

    app.router.routes.insert(0, app.router.routes.pop())

    with TestClient(
        app, base_url="https://portal.example", raise_server_exceptions=False
    ) as c:
        assert (
            c.post(
                "/api/v1/auth/login",
                headers={"Host": "evil.example", "Origin": "https://evil.example"},
                json={"username": "admin", "password": "Fixture-Strong-Password-42"},
            ).status_code
            == 400
        )
        assert (
            c.post(
                "/api/v1/auth/login",
                headers={"Origin": "https://evil.example"},
                json={"username": "admin", "password": "Fixture-Strong-Password-42"},
            ).status_code
            == 403
        )
        result = c.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Fixture-Strong-Password-42"},
        )
        assert (
            result.status_code == 200
            and "__Host-aptilume_session=" in result.headers["set-cookie"]
            and "Secure" in result.headers["set-cookie"]
        )
        duplicate = c.get(
            "/api/v1/auth/me",
            headers={"Cookie": "__Host-aptilume_session=a; __Host-aptilume_session=b"},
        )
        assert duplicate.status_code == 400
        # Allow the test endpoint via business role to exercise sanitizing all exception paths.
        with store.cs() as s:
            s.get(DirectoryUser, "local-admin").roles = ["hr"]
        error = c.get("/api/v1/crash-fixture")
        assert (
            error.status_code == 500 and "private-connection-secret" not in error.text
        )
        assert (
            error.headers["x-request-id"] and error.headers["content-security-policy"]
        )


def test_session_count_is_bounded_under_parallel_creation(store):
    auth = AuthService(store)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: auth.create_session("local-admin"), range(16)))
    with store.cs() as s:
        assert len(list(s.scalars(select(AuthSession)))) == 5


@pytest.mark.parametrize(
    "value",
    [
        "aaaaaaaaaaaaaaa",
        "123456789012345",
        "admin-strong-password-42",
        "too-short",
        " leading-whitespace-long-password",
    ],
)
def test_predictable_passwords_rejected(value):
    assert not strong_password(value)


def test_exports_quota_and_tamper_check(store, scoped):
    _, as_user = scoped
    _, _, pid = publication(store)
    with as_user("hr") as c:
        ids = []
        for _ in range(5):
            r = c.post("/api/v1/exports", json={"publication_id": pid, "detail": True})
            assert r.status_code == 202
            ids.append(r.json()["id"])
        assert (
            c.post("/api/v1/exports", json={"publication_id": pid}).status_code == 429
        )
        Worker(store).drain()
        with store.session() as s:
            artifact = s.get(Export, ids[0])
            path = artifact.file
            with open(path, "ab") as f:
                f.write(b"changed-fixture")
        assert c.get("/api/v1/exports/" + ids[0] + "/download").status_code == 409


def test_retention_expires_artifacts_and_removes_auth_metadata(store, scoped):
    _, as_user = scoped
    _, _, pid = publication(store)
    with as_user("hr") as c:
        eid = c.post("/api/v1/exports", json={"publication_id": pid}).json()["id"]
        Worker(store).drain()
        with store.session() as s:
            artifact = s.get(Export, eid)
            path = artifact.file
            artifact.created_at = (
                datetime.now(timezone.utc) - timedelta(days=8)
            ).isoformat()
        with store.cs() as s:
            s.add(
                RateBucket(
                    key="expired-fixture", count=1, expires_at=time.time() - 3600
                )
            )
        cleanup(store)
        assert c.get("/api/v1/exports/" + eid + "/download").status_code == 409
        assert not __import__("pathlib").Path(path).exists()
        with store.cs() as s:
            assert s.get(RateBucket, "expired-fixture") is None


@pytest.mark.parametrize("kind", ["header", "stream", "compressed"])
def test_llm_response_budget_and_encoding(store, kind):
    class Chunks(httpx.SyncByteStream):
        def __iter__(self):
            yield b"x" * 600000
            yield b"x" * 600000

    def handler(request):
        assert request.headers["accept-encoding"] == "identity"
        if kind == "header":
            return httpx.Response(
                200, headers={"content-length": "2000000"}, stream=Chunks()
            )
        if kind == "compressed":
            return httpx.Response(
                200, headers={"content-encoding": "gzip"}, stream=Chunks()
            )
        return httpx.Response(200, stream=Chunks())

    p = Provider(
        {
            "provider": "openai_compatible_chat",
            "model": "fixture",
            "endpoint": "https://llm.example/v1",
        },
        "llm.example",
        httpx.MockTransport(handler),
    )
    with pytest.raises(DomainError):
        p.complete("test", {})


def test_actual_http_request_uses_validated_ip_and_tls_hostname(monkeypatch):
    import app.providers as providers

    seen = {}

    class FakeResponse:
        headers = {}
        is_stream_consumed = False

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def raise_for_status(self):
            pass

        def iter_raw(self):
            yield b'{"choices":[{"message":{"content":"{\\"ok\\":true}"},"finish_reason":"stop"}]}'

    class Client:
        def __init__(self, **kw):
            seen.update(kw)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def stream(self, method, url, **kw):
            seen["url"] = url
            seen.update(kw)
            return FakeResponse()

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 443))
        ],
    )
    monkeypatch.setattr(providers.httpx, "Client", Client)
    result, _ = Provider(
        {
            "provider": "openai_compatible_chat",
            "model": "fixture",
            "endpoint": "https://llm.example/v1",
        },
        "llm.example",
    ).complete("test", {})
    assert (
        result == {"ok": True}
        and str(seen["url"]) == "https://93.184.216.34/v1/chat/completions"
    )
    assert (
        seen["headers"]["Host"] == "llm.example"
        and seen["extensions"]["sni_hostname"] == "llm.example"
    )
    assert seen["trust_env"] is False and seen["follow_redirects"] is False


def test_self_review_and_duplicate_decision_are_blocked(store, scoped):
    _, as_user = scoped
    cfg = store.save_profile(
        "llm",
        "Review fixture",
        {"provider": "mock", "model": "fixture", "scenario": "unsupported_quote"},
    )
    store.bind("evaluation", cfg["id"])
    cid = open_campaign(store)
    seed_answers(store, cid, 10)
    campaign_transition(store, cid, "close")
    run = start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        rows = list(
            s.execute(
                select(Evaluation.id, Assignment.participant_id)
                .join(Answer, Answer.id == Evaluation.answer_id)
                .join(Assignment, Assignment.id == Answer.assignment_id)
                .where(
                    Evaluation.run_id == run["id"],
                    Evaluation.review_status == "pending",
                )
            )
        )
        own = next(eid for eid, pid in rows if pid == P(1))
        other = next(eid for eid, pid in rows if pid == P(3))
    with as_user("m1") as c:
        assert (
            c.post(
                "/api/v1/reviews/" + own + "/decision",
                json={"reason": "Own response test", "score": 100},
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/v1/reviews/" + other + "/decision",
                json={"reason": "Independent review", "score": 50},
            ).status_code
            == 200
        )
        assert (
            c.post(
                "/api/v1/reviews/" + other + "/decision",
                json={"reason": "Second overwrite", "score": 100},
            ).status_code
            == 409
        )


def test_security_events_are_hr_only_and_exclude_private_payload(store, scoped):
    _, as_user = scoped
    with as_user("ia") as c:
        assert c.get("/api/v1/admin/security-events").status_code == 403
        c.post(
            "/api/v1/admin/connections/llm",
            json={
                "name": "Audit fixture",
                "config": {"provider": "mock", "model": "fixture"},
                "secret": "never-log-this-fixture-secret",
            },
        )
    with as_user("hr") as c:
        r = c.get("/api/v1/admin/security-events")
        assert (
            r.status_code == 200
            and "sensitive_operation" in r.text
            and "never-log-this-fixture-secret" not in r.text
        )


@pytest.mark.parametrize(
    "body",
    [
        b'{"username":"admin","username":"other","password":"admin"}',
        b'{"score":NaN}',
        b"[" * 40 + b"0" + b"]" * 40,
        b'{"value":1e999}',
    ],
)
def test_ambiguous_nonfinite_and_deep_json_are_rejected(store, body):
    with TestClient(create_app(store=store)) as c:
        result = c.post(
            "/api/v1/auth/login",
            content=body,
            headers={"Content-Type": "application/json"},
        )
        assert result.status_code == 400 and result.json()["code"] == "invalid_json"


def test_nested_ad_membership_uses_bounded_group_queries(monkeypatch):
    from types import SimpleNamespace
    from app.directory import DirectoryClient, DEFAULT_DIRECTORY

    calls = []
    users = [
        {
            "type": "searchResEntry",
            "dn": "cn=u" + str(i),
            "attributes": {
                "objectGUID": str(UUID(int=i + 1)),
                "sAMAccountName": "u" + str(i),
                "userAccountControl": 512,
            },
        }
        for i in range(100)
    ]

    def search(base, query, *a, **kw):
        calls.append(query)
        return users if ":1.2.840." not in query else users[:1]

    class Conn:
        result = {"result": 0}
        extend = SimpleNamespace(standard=SimpleNamespace(paged_search=search))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    c = DirectoryClient(
        {
            **DEFAULT_DIRECTORY,
            "role_groups": {"hr": ["cn=hr"], "admin": ["cn=admins"], "manager": []},
            "nested_groups": True,
        }
    )
    monkeypatch.setattr(c, "service", lambda: Conn())
    result = c.snapshot()
    assert (
        len(calls) == 3
        and result[0]["roles"] == ["hr"]
        and result[-1]["roles"] == ["employee"]
    )


def test_production_accepts_native_pod_probe_host_without_relaxing_api(
    store, monkeypatch
):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Fixture-Strong-Password-42")
    store.settings.demo = False
    store.settings.public_base_url = "https://portal.example"
    with TestClient(create_app(store=store), base_url="http://10.42.1.7:8080") as c:
        assert c.get("/health/ready").status_code == 200
        assert c.get("/api/v1/bootstrap").status_code == 400


def test_admin_recovery_does_not_depend_on_application_database(store, scoped):
    _, as_user = scoped
    with store.cs() as s:
        binding = s.get(Binding, "application_db")
        s.get(ProfileVersion, binding.version_id).config = {
            "engine": "sqlite",
            "path": "/invalid/outside/application.db",
        }
    store._binding_version = None
    with as_user("ia") as c:
        r = c.get("/api/v1/bootstrap")
        assert r.status_code == 200 and r.json()["participants"] == []
        assert c.get("/api/v1/admin/connections/db").status_code == 200
    with as_user("hr") as c:
        r = c.get("/api/v1/bootstrap")
        assert (
            r.status_code == 200
            and r.json()["degraded"]
            and r.json()["participants"] == []
        )

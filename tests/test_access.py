"""Adversarial coverage for sessions, AD identity and server-side data scope."""

import copy
import hashlib
import ssl
import time
from contextlib import contextmanager
from uuid import UUID

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from ldap3 import Connection, MOCK_SYNC, Server
from openpyxl import load_workbook
from sqlalchemy import select

from app.api import create_app
from app.config import Settings
from app.directory import (
    DEFAULT_DIRECTORY,
    DirectoryClient,
    directory_config,
    save_directory_config,
    synchronize,
)
from app.models import AuthSession, DirectoryUser, Export, Participant, Setting, Team
from app.reporting import publish
from app.security import AuthService, COOKIE, actor_for_user
from app.services import (
    assignments,
    campaign_transition,
    create_campaign,
    enqueue_generation,
    form,
    seed_answers,
    start_run,
)
from app.store import DomainError, Store
from app.worker import Worker

P = lambda i: f"team-data-person-{i:02}"


@pytest.fixture
def scoped(store):
    app = create_app(store=store)
    entries = [
        ("m1", "manager", 1, ""),
        ("m2", "manager", 2, ""),
        ("e1", "employee", 3, "m1"),
        ("e2", "employee", 4, "m2"),
        ("lead", "manager", 5, "m1"),
        ("e3", "employee", 6, "lead"),
        ("hr", "hr", None, ""),
        ("ia", "admin", None, ""),
    ]
    with store.cs() as s:
        for name, role, pid, manager in entries:
            s.add(
                DirectoryUser(
                    id=name,
                    username=name,
                    display_name=name,
                    roles=[role],
                    groups=[],
                    participant_id=P(pid) if pid else None,
                    dn=f"cn={name}",
                    manager_dn=f"cn={manager}" if manager else "",
                    source="local",
                )
            )

    @contextmanager
    def as_user(name):
        token, actor = app.state.auth.create_session(name)
        with TestClient(app) as c:
            c.cookies.set(COOKIE, token)
            c.headers["X-CSRF-Token"] = actor.csrf_token
            yield c

    return app, as_user


def open_campaign(store):
    cid = create_campaign(store, "Access test", ["team-data"])["id"]
    enqueue_generation(store, cid)
    Worker(store).drain()
    campaign_transition(store, cid, "approve")
    campaign_transition(store, cid, "open")
    return cid


def publication(store):
    cid = open_campaign(store)
    seed_answers(store, cid, 10)
    campaign_transition(store, cid, "close")
    run = start_run(store, cid)
    Worker(store).drain()
    pub = publish(store, run["id"])
    return cid, run["id"], pub


def test_anonymous_and_integration_admin_cannot_access_business(store, scoped):
    app, as_user = scoped
    with TestClient(app) as c:
        assert c.get("/api/v1/bootstrap").status_code == 401
        assert c.get("/api/v1/admin/directory").status_code == 401
    with as_user("ia") as c:
        boot = c.get("/api/v1/bootstrap").json()
        assert not boot["participants"] and not boot["teams"] and not boot["campaigns"]
        for path in [
            "/skills",
            "/me/profile",
            "/development-actions",
            "/evaluation-runs",
            "/jobs",
            "/exports",
        ]:
            assert c.get("/api/v1" + path).status_code == 403
        assert c.get("/api/v1/admin/directory").status_code == 200
        assert c.get("/api/v1/admin/connections/llm").status_code == 200


def test_local_login_csrf_rotation_logout_and_origin(store):
    app = create_app(store=store)
    with TestClient(app) as c:
        first = c.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert first.status_code == 200
        cookie = first.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        token = c.cookies.get(COOKIE)
        csrf = first.json()["csrf_token"]
        assert (
            c.put("/api/v1/settings/workspace", json={"name": "Changed"}).status_code
            == 403
        )
        assert (
            c.put(
                "/api/v1/settings/workspace",
                json={"name": "Changed"},
                headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        second = c.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert c.cookies.get(COOKIE) != token
        with pytest.raises(DomainError):
            app.state.auth.actor(token)
        assert (
            c.post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": second.json()["csrf_token"]},
            ).status_code
            == 200
        )
        assert c.get("/api/v1/auth/me").status_code == 401
        with store.cs() as s:
            assert s.get(DirectoryUser, "local-admin").password_hash.startswith(
                "$argon2"
            )
            assert not s.get(AuthSession, token)


def test_login_throttle_and_production_bootstrap(store, tmp_path, monkeypatch):
    auth = AuthService(store)
    for _ in range(5):
        with pytest.raises(DomainError) as err:
            auth.login("admin", "wrong", "127.0.0.1")
        assert err.value.status == 401
    with pytest.raises(DomainError) as err:
        auth.login("admin", "admin", "127.0.0.1")
    assert err.value.status == 429
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    prod = Store(
        Settings(
            tmp_path / "prod",
            f"sqlite:///{tmp_path/'prod-control.db'}",
            Fernet.generate_key().decode(),
            demo=False,
            public_base_url="https://testserver",
        )
    )
    with pytest.raises(RuntimeError):
        AuthService(prod)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "Fixture-Strong-Password-42")
    secure = AuthService(prod)
    token, actor = secure.login("admin", "Fixture-Strong-Password-42", "test")
    assert not actor.temporary_password
    with pytest.raises(DomainError):
        prod.resolve("evaluation")
    c = TestClient(
        create_app(store=prod, auth_service=secure), base_url="https://testserver"
    )
    r = c.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Fixture-Strong-Password-42"},
    )
    assert "Secure" in r.headers["set-cookie"]
    assert c.get("/docs").status_code == 404


def test_idle_background_polling_and_live_role_revocation(store, scoped):
    app, as_user = scoped
    token, _ = app.state.auth.create_session("e1")
    hashed = hashlib.sha256(token.encode()).hexdigest()
    old = time.time() - 1700
    with store.cs() as s:
        s.get(AuthSession, hashed).last_seen = old
    app.state.auth.actor(token, touch=False)
    with store.cs() as s:
        assert s.get(AuthSession, hashed).last_seen == old
    with as_user("m1") as c:
        assert len(c.get("/api/v1/bootstrap").json()["participants"]) == 4
        with store.cs() as s:
            s.get(DirectoryUser, "m1").roles = ["employee"]
        assert len(c.get("/api/v1/bootstrap").json()["participants"]) == 1
        with store.cs() as s:
            s.get(DirectoryUser, "m1").active = False
        assert c.get("/api/v1/bootstrap").status_code == 401
    with store.cs() as s:
        s.get(AuthSession, hashed).last_seen = time.time() - 1801
    with pytest.raises(DomainError):
        app.state.auth.actor(token, touch=False)


def test_shared_department_scopes_are_reporting_tree_based(store, scoped):
    _, as_user = scoped
    with as_user("m1") as c:
        b = c.get("/api/v1/bootstrap").json()
        assert {p["id"] for p in b["participants"]} == {P(1), P(3), P(5), P(6)}
        assert not b["editable_team_ids"]
        assert (
            c.patch(
                "/api/v1/teams/team-data",
                json={"name": "hijack", "role": "role", "targets": []},
            ).status_code
            == 403
        )
        assert c.get("/api/v1/admin/directory").status_code == 403
        assert c.get("/api/v1/jobs").status_code == 403
    with as_user("e2") as c:
        assert [p["id"] for p in c.get("/api/v1/bootstrap").json()["participants"]] == [
            P(4)
        ]
        assert c.get("/api/v1/role-profiles").status_code == 403
    with as_user("hr") as c:
        assert len(c.get("/api/v1/bootstrap").json()["participants"]) == 30
        assert c.get("/api/v1/admin/directory").status_code == 200


def test_idor_on_forms_answers_and_manager_campaign_mutations(store, scoped):
    _, as_user = scoped
    cid = open_campaign(store)
    aa = {a["participant_id"]: a for a in assignments(store, cid)}
    own, other = aa[P(3)]["id"], aa[P(4)]["id"]
    q = form(store, own)["questions"][0]["id"]
    with as_user("e1") as c:
        assert c.get(f"/api/v1/assignments/{other}/form").status_code == 404
        assert (
            c.put(
                f"/api/v1/assignments/{other}/answers/{q}", json={"text": "attack"}
            ).status_code
            == 403
        )
        assert c.post(f"/api/v1/assignments/{other}/submit").status_code == 403
        data = c.get(f"/api/v1/assignments/{own}/form").json()
        assert data["can_answer"] and "rubric" not in str(data["questions"])
        assert (
            c.put(
                f"/api/v1/assignments/{own}/answers/{q}",
                json={"text": "Own answer", "revision": 0},
            ).status_code
            == 200
        )
    with as_user("m1") as c:
        listing = c.get(f"/api/v1/campaigns/{cid}/assignments").json()
        assert {a["participant_id"] for a in listing} == {P(1), P(3), P(5), P(6)}
        assert not c.get(f"/api/v1/assignments/{own}/form").json()["can_answer"]
        for suffix in ["close", "evaluation-runs", "generate-questions"]:
            assert c.post(f"/api/v1/campaigns/{cid}/{suffix}").status_code == 403
        assert c.get(f"/api/v1/campaigns/{cid}/questions").status_code == 403
    with as_user("hr") as c:
        assert c.post(f"/api/v1/assignments/{own}/submit").status_code == 403


def test_manager_campaign_captures_only_owned_people(store, scoped):
    _, as_user = scoped
    with as_user("m1") as c:
        assert (
            c.post(
                "/api/v1/campaigns",
                json={"name": "Forged", "team_ids": ["team-software"]},
            ).status_code
            == 403
        )
        result = c.post("/api/v1/campaigns", json={"name": "Own reports"})
        assert result.status_code == 200
        cid = result.json()["id"]
        assert set(result.json()["config"]["participant_ids"]) == {
            P(1),
            P(3),
            P(5),
            P(6),
        }
        assert c.post(f"/api/v1/campaigns/{cid}/generate-questions").status_code == 202
        Worker(store).drain()
        version = c.get(f"/api/v1/campaigns/{cid}/question-set").json()["version"]
        assert (
            c.post(
                f"/api/v1/campaigns/{cid}/approve", json={"expected_version": version}
            ).status_code
            == 403
        )
        assert (
            c.post(
                f"/api/v1/campaigns/{cid}/open", json={"expected_version": version}
            ).status_code
            == 403
        )
        with as_user("hr") as hr:
            approved = hr.post(
                f"/api/v1/campaigns/{cid}/approve", json={"expected_version": version}
            )
            assert approved.status_code == 200
            assert (
                hr.post(
                    f"/api/v1/campaigns/{cid}/open",
                    json={"expected_version": approved.json()["row_version"]},
                ).status_code
                == 200
            )
        assert {a["participant_id"] for a in assignments(store, cid)} == {
            P(1),
            P(3),
            P(5),
            P(6),
        }
    with as_user("m2") as c:
        assert c.get(f"/api/v1/campaigns/{cid}/assignments").status_code == 404


def test_report_export_and_jobs_scope_rechecked_after_hierarchy_change(store, scoped):
    _, as_user = scoped
    cid, rid, pid = publication(store)
    with as_user("m1") as c:
        report = c.get(f"/api/v1/reports/{pid}").json()
        assert {r["participant_id"] for r in report["rows"]} == {P(1), P(3), P(5), P(6)}
        assert c.get(f"/api/v1/reports/{pid}?team_id=team-software").status_code == 404
        run = c.get("/api/v1/evaluation-runs").json()[0]
        assert not run["can_manage"]
        assert (
            "input_manifest" not in run
            and "insights" not in run
            and "profile_version" not in run
        )
        assert c.post(f"/api/v1/evaluation-runs/{rid}/publish").status_code == 403
        assert (
            c.post(
                "/api/v1/exports",
                json={"publication_id": pid, "filters": {"team_id": "team-software"}},
            ).status_code
            == 404
        )
        result = c.post(
            "/api/v1/exports",
            json={
                "publication_id": pid,
                "detail": True,
                "filters": {"participant_ids": [P(4)], "all": True},
            },
        )
        assert result.status_code == 202
        eid = result.json()["id"]
        Worker(store).drain()
        assert c.get(f"/api/v1/exports/{eid}/download").status_code == 200
        with store.session() as s:
            export = s.get(Export, eid)
            wb = load_workbook(export.file)
            ws = wb["Kisi_Yetkinlik"]
            assert {row[0] for row in list(ws.values)[1:]} == {P(1), P(3), P(5), P(6)}
        with store.cs() as s:
            s.get(DirectoryUser, "e1").manager_dn = "cn=m2"
        assert c.get(f"/api/v1/exports/{eid}/download").status_code == 404
        assert not c.get("/api/v1/exports").json()
    with as_user("e2") as c:
        assert {
            r["participant_id"] for r in c.get(f"/api/v1/reports/{pid}").json()["rows"]
        } == {P(4)}
        assert c.get(f"/api/v1/exports/{eid}/download").status_code == 404
        assert all(
            {r["participant_id"] for r in pub["rows"]} == {P(4)}
            for pub in c.get("/api/v1/me/results").json()
        )


def test_development_plans_persist_enforce_scope_and_revisions(store, scoped):
    _, as_user = scoped
    item = {
        "title": "Applied RAG practice",
        "owner_name": "Team manager",
        "participant_id": P(3),
        "skill_id": "SKILL-001",
        "status": "planned",
    }
    with as_user("m1") as c:
        assert (
            c.post(
                "/api/v1/development-actions", json={**item, "participant_id": P(4)}
            ).status_code
            == 404
        )
        assert (
            c.post(
                "/api/v1/development-actions",
                json={**item, "participant_id": None, "team_id": "team-data"},
            ).status_code
            == 403
        )
        r = c.post("/api/v1/development-actions", json=item)
        assert r.status_code == 200
        result = r.json()
        aid = result["id"]
        assert (
            c.patch(
                f"/api/v1/development-actions/{aid}",
                json={
                    **item,
                    "status": "in_progress",
                    "row_version": result["row_version"],
                },
            ).status_code
            == 200
        )
        assert (
            c.patch(
                f"/api/v1/development-actions/{aid}", json={**item, "row_version": 1}
            ).status_code
            == 409
        )
    with as_user("e1") as c:
        assert len(c.get("/api/v1/development-actions").json()) == 1
        assert c.post("/api/v1/development-actions", json=item).status_code == 403
    with as_user("m2") as c:
        assert not c.get("/api/v1/development-actions").json()
        assert (
            c.patch(
                f"/api/v1/development-actions/{aid}", json={**item, "row_version": 2}
            ).status_code
            == 404
        )


class FakeDirectory:
    rows = []

    def __init__(self, config):
        self.config = config

    def snapshot(self):
        return copy.deepcopy(self.rows)

    def authenticate(self, username, password):
        if username != "employee" or password != "directory-password":
            raise DomainError("invalid_credentials", "Invalid", 401)
        return self.rows[1]

    def test(self):
        return None


def directory_rows():
    return [
        dict(
            id="ad:" + str(UUID(int=i)),
            username=name,
            dn=f"cn={name}",
            manager_dn="cn=manager" if i == 2 else "",
            display_name=name,
            email=f"{name}@example.test",
            department="AD Team",
            title="Engineer",
            groups=[],
            active=True,
            roles=[role],
        )
        for i, name, role in [(1, "manager", "manager"), (2, "employee", "employee")]
    ]


def configure(store):
    save_directory_config(
        store,
        {
            "enabled": True,
            "host": "ad.example.test",
            "base_dn": "dc=example,dc=test",
            "bind_dn": "cn=service",
            "password": "fixture-secret",
        },
    )


def test_ad_login_sync_identity_secret_redaction_and_disable(store):
    FakeDirectory.rows = directory_rows()
    auth = AuthService(store, FakeDirectory)
    app = create_app(store=store, auth_service=auth)
    configure(store)
    with TestClient(app) as c:
        r = c.post(
            "/api/v1/auth/login",
            json={"username": "employee", "password": "directory-password"},
        )
        assert r.status_code == 200 and r.json()["roles"] == ["employee"]
        own = r.json()["participant_id"]
        assert own == FakeDirectory.rows[1]["id"]
        assert len(c.get("/api/v1/bootstrap").json()["participants"]) == 1
        FakeDirectory.rows[1]["active"] = False
        auth.refresh_directory(force=True)
        assert c.get("/api/v1/auth/me").status_code == 401
    safe = directory_config(store)
    assert (
        safe["has_secret"]
        and "fixture-secret" not in str(safe)
        and "encrypted_password" not in safe
    )
    with store.cs() as s:
        assert "fixture-secret" not in str(s.get(Setting, "directory").value)
        assert s.get(DirectoryUser, own).password_hash is None
    FakeDirectory.rows = directory_rows()
    synchronize(store, FakeDirectory)
    token, _ = auth.create_session(own)
    save_directory_config(store, {"include_descendants": False})
    with pytest.raises(DomainError):
        auth.actor(token)
    with pytest.raises(DomainError):
        save_directory_config(store, {"host": "other.example.test"})


@pytest.mark.parametrize(
    "bad",
    [
        {"port": "oops"},
        {"role_groups": []},
        {"enabled": "false"},
        {"transport": "plain"},
        {"manager_attribute": "manager)(x=*"},
        {"department_map": {"Dept": 42}},
    ],
)
def test_invalid_ad_settings_are_rejected(store, bad):
    with pytest.raises(DomainError):
        save_directory_config(store, bad)


def test_ad_cycle_rejected_without_partial_identity_changes(store):
    configure(store)
    FakeDirectory.rows = directory_rows()
    FakeDirectory.rows[0]["manager_dn"] = "cn=employee"
    with pytest.raises(DomainError) as err:
        synchronize(store, FakeDirectory)
    assert err.value.code == "directory_cycle"
    with store.cs() as s:
        assert not list(s.scalars(select(DirectoryUser)))


def test_ldap_filter_escaping_and_real_mock_bind(monkeypatch):
    cfg = {
        **DEFAULT_DIRECTORY,
        "host": "ad.example.test",
        "base_dn": "dc=example,dc=test",
        "bind_dn": "cn=service",
        "password": "fixture",
    }
    client = DirectoryClient(cfg)
    conn = Connection(Server("mock"), client_strategy=MOCK_SYNC, check_names=False)
    conn.strategy.add_entry(
        "cn=service", {"userPassword": "fixture", "objectClass": "user"}
    )
    dn = "cn=employee,dc=example,dc=test"
    conn.strategy.add_entry(
        dn,
        {
            "objectClass": "user",
            "objectCategory": "person",
            "sAMAccountName": "employee",
            "userPassword": "user-password",
            "objectGUID": str(UUID(int=7)),
            "manager": "cn=manager",
            "displayName": "Employee",
            "department": "IT",
            "userAccountControl": 512,
        },
    )

    def connect(user, password):
        bound = Connection(
            conn.server,
            user=user,
            password=password,
            client_strategy=MOCK_SYNC,
            check_names=False,
            raise_exceptions=True,
        )
        bound.strategy.entries = conn.strategy.entries
        bound.bind()
        return bound

    monkeypatch.setattr(client, "connect", connect)
    result = client.authenticate("employee", "user-password")
    assert result["id"] == "ad:" + str(UUID(int=7))
    with pytest.raises(DomainError):
        client.authenticate("*)(sAMAccountName=*)", "user-password")
    with pytest.raises(DomainError):
        client.authenticate("employee", "wrong")


def test_ldap_transport_requires_verified_tls(monkeypatch):
    captured = {}

    def server(host, **kwargs):
        captured.update(kwargs)
        return object()

    def connection(server, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("app.directory.Server", server)
    monkeypatch.setattr("app.directory.Connection", connection)
    cfg = {**DEFAULT_DIRECTORY, "host": "ad.example.test"}
    DirectoryClient(cfg).connect("user", "password")
    assert captured["use_ssl"] and captured["tls"].validate == ssl.CERT_REQUIRED
    assert captured["auto_referrals"] is False


def test_disabled_directory_and_outage_fail_closed_for_existing_session(store):
    configure(store)
    FakeDirectory.rows = directory_rows()
    auth = AuthService(store, FakeDirectory)
    auth.refresh_directory(force=True)
    token, _ = auth.create_session(FakeDirectory.rows[1]["id"])
    with store.cs() as s:
        s.get(Setting, "directory_sync").value = {"last_sync": 0}

    class Unavailable(FakeDirectory):
        def snapshot(self):
            raise DomainError("directory_unavailable", "Offline", 503)

    auth.client_factory = Unavailable
    with pytest.raises(DomainError) as err:
        auth.actor(token)
    assert err.value.status == 503
    save_directory_config(store, {"enabled": False})
    with pytest.raises(DomainError):
        auth.actor(token)


def test_direct_reports_option_and_scope_revision(store, scoped):
    before = actor_for_user(store, "m1")
    save_directory_config(store, {"include_descendants": False})
    after = actor_for_user(store, "m1")
    assert after.participant_ids == frozenset({P(1), P(3), P(5)})
    assert before.public()["scope_revision"] != after.public()["scope_revision"]


def test_admin_password_change_revokes_all_sessions_and_protects_production(store):
    auth = AuthService(store)
    t1, a = auth.login("admin", "admin", "test")
    t2, _ = auth.login("admin", "admin", "test")
    with pytest.raises(DomainError):
        auth.change_password(a, "incorrect", "A-strong-password-42")
    auth.change_password(a, "admin", "A-strong-password-42")
    for token in [t1, t2]:
        with pytest.raises(DomainError):
            auth.actor(token)
    assert not auth.login("admin", "A-strong-password-42", "test")[1].temporary_password
    store.settings.demo = False
    AuthService(store)


def test_ad_group_role_precedence_and_automatic_manager(monkeypatch):
    from types import SimpleNamespace

    cfg = {
        **DEFAULT_DIRECTORY,
        "role_groups": {"hr": ["cn=hr"], "admin": ["cn=admins"], "manager": []},
        "nested_groups": False,
    }

    def row(n, groups, manager=""):
        return {
            "type": "searchResEntry",
            "dn": f"cn=u{n}",
            "attributes": {
                "objectGUID": str(UUID(int=n)),
                "sAMAccountName": f"u{n}",
                "memberOf": groups,
                "manager": manager,
                "userAccountControl": 512,
            },
        }

    rows = [
        row(1, ["cn=hr", "cn=admins"]),
        row(2, ["cn=admins"]),
        row(3, [], "cn=u2"),
        row(4, [], "cn=u3"),
        row(5, []),
    ]

    class ConnectionFixture:
        result = {"result": 0}
        extend = SimpleNamespace(
            standard=SimpleNamespace(paged_search=lambda *a, **kw: rows)
        )

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    client = DirectoryClient(cfg)
    monkeypatch.setattr(client, "service", lambda: ConnectionFixture())
    mapped = {u["username"]: u["roles"] for u in client.snapshot()}
    assert mapped == {
        "u1": ["hr"],
        "u2": ["admin"],
        "u3": ["manager"],
        "u4": ["employee"],
        "u5": ["employee"],
    }

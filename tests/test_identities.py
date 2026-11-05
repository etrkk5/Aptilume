"""Local identity provisioning cannot bypass business scopes or provider ownership."""

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api import create_app
from app.models import DirectoryUser, AuthSession, ControlEvent
from app.security import AuthService

PASSWORD = "Fixture-users-password-72!"
P = lambda i: f"team-data-person-{i:02}"


@pytest.fixture
def identities(store, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_HR_PASSWORD", PASSWORD)
    app = create_app(store=store)

    def login(name="hr", password=PASSWORD):
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/login", json={"username": name, "password": password}
        )
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        return client

    return app, login


def create(client, name, role="admin", participant=None, manager=None, version=None):
    return client.post(
        "/api/v1/admin/users",
        json={
            "expected_version": version
            or client.get("/api/v1/admin/users").json()["version"],
            "username": name,
            "display_name": name + " display",
            "password": PASSWORD,
            "role": role,
            "participant_id": participant,
            "manager_id": manager,
        },
    )


def edit(client, user_id, **changes):
    listing = client.get("/api/v1/admin/users").json()
    user = next(u for u in listing["items"] if u["id"] == user_id)
    payload = {
        k: user[k]
        for k in ["display_name", "email", "participant_id", "manager_id", "active"]
    }
    payload.update(role=user["roles"][0], expected_version=listing["version"])
    payload.update(changes)
    return client.put("/api/v1/admin/users/" + user_id, json=payload)


def test_provider_independent_manager_and_employee_logins_have_exact_scope(identities):
    app, login = identities
    hr = login()
    manager = create(hr, "lead.one", "manager", P(1)).json()["id"]
    employee = create(hr, "person.two", "employee", P(2), manager)
    assert employee.status_code == 201
    assert create(hr, "person.other", "employee", P(3)).status_code == 201
    lead = login("LEAD.ONE")
    assert {p["id"] for p in lead.get("/api/v1/bootstrap").json()["participants"]} == {
        P(1),
        P(2),
    }
    person = login("person.two")
    assert {
        p["id"] for p in person.get("/api/v1/bootstrap").json()["participants"]
    } == {P(2)}
    assert lead.get("/api/v1/admin/users").status_code == 403
    assert person.get("/api/v1/admin/users").status_code == 403
    assert lead.get("/api/v1/admin/connections/db").status_code == 403


def test_integration_admin_cannot_reset_or_provision_business_identity(identities):
    app, login = identities
    hr = login()
    target = create(hr, "private.person", "employee", P(2)).json()["id"]
    admin = login("admin", "admin")
    listing = admin.get("/api/v1/admin/users").json()
    assert listing["allowed_roles"] == ["admin"] and not listing["managers"]
    assert all(u["roles"] == ["admin"] for u in listing["items"])
    assert "private.person" not in str(listing) and P(2) not in str(listing)
    assert create(admin, "forged.hr", "hr").status_code == 403
    assert create(admin, "forged.employee", "employee", P(3)).status_code == 403
    payload = {
        "expected_version": listing["version"],
        "display_name": "Forged",
        "role": "admin",
        "password": PASSWORD,
    }
    assert admin.put("/api/v1/admin/users/" + target, json=payload).status_code == 403
    assert admin.put("/api/v1/admin/users/local-hr", json=payload).status_code == 403
    assert create(admin, "operator.two").status_code == 201
    assert login("operator.two").get("/api/v1/skills").status_code == 403


def test_password_rotation_and_disable_revoke_sessions_without_reset_on_restart(
    identities, store
):
    app, login = identities
    hr = login()
    target = create(hr, "local.employee", "employee", P(2)).json()["id"]
    employee = login("local.employee")
    assert employee.get("/api/v1/auth/me").json()["can_change_password"]
    assert edit(hr, target, password="Fixture-rotated-user-93!").status_code == 200
    assert employee.get("/api/v1/auth/me").status_code == 401
    assert (
        employee.post(
            "/api/v1/auth/login",
            json={"username": "local.employee", "password": PASSWORD},
        ).status_code
        == 401
    )
    active = login("local.employee", "Fixture-rotated-user-93!")
    assert (
        active.post(
            "/api/v1/auth/password",
            json={
                "current_password": "Fixture-rotated-user-93!",
                "new_password": "Fixture-personal-user-94!",
            },
        ).status_code
        == 200
    )
    assert active.get("/api/v1/auth/me").status_code == 401
    assert edit(hr, target, active=False).status_code == 200
    AuthService(store)
    denied = TestClient(app).post(
        "/api/v1/auth/login",
        json={"username": "local.employee", "password": "Fixture-personal-user-94!"},
    )
    assert denied.status_code == 401
    with store.cs() as session:
        user = session.get(DirectoryUser, target)
        assert not user.active and user.password_hash.startswith("$argon2")
        events = [
            e.detail
            for e in session.scalars(
                select(ControlEvent).where(ControlEvent.profile_id == target)
            )
        ]
        assert events and PASSWORD not in str(events) and "$argon2" not in str(events)


def test_account_versions_prevent_lost_updates_and_failed_create_rolls_back(
    identities, store
):
    app, login = identities
    hr = login()
    initial = hr.get("/api/v1/admin/users").json()
    assert create(hr, "operator.one", version=initial["version"]).status_code == 201
    stale = create(hr, "operator.stale", version=initial["version"])
    assert stale.status_code == 409 and stale.json()["code"] == "identity_conflict"
    current = hr.get("/api/v1/admin/users").json()
    failed = create(hr, "missing.profile", "employee", "missing-id")
    assert failed.status_code == 404
    assert hr.get("/api/v1/admin/users").json()["version"] == current["version"]
    assert create(hr, "operator.one").status_code == 409
    assert create(hr, "admin").status_code == 409
    with store.cs() as session:
        assert not session.scalar(
            select(DirectoryUser.id).where(DirectoryUser.username == "missing.profile")
        )


def test_profile_aliases_cycles_and_provider_mutation_are_rejected(identities, store):
    app, login = identities
    hr = login()
    one = create(hr, "manager.one", "manager", P(1)).json()["id"]
    two = create(hr, "manager.two", "manager", P(2), one).json()["id"]
    assert create(hr, "profile.alias", "employee", P(2)).status_code == 409
    assert edit(hr, one, manager_id=two).json()["code"] == "manager_cycle"
    assert edit(hr, one, manager_id=one).json()["code"] == "manager_cycle"
    assert edit(hr, one, role="employee").json()["code"] == "manager_has_reports"
    with store.cs() as session:
        session.add(
            DirectoryUser(
                id="external",
                username="ad:person",
                display_name="External",
                roles=["employee"],
                source="ldap",
                participant_id=P(4),
            )
        )
    result = edit(hr, "external", password=PASSWORD)
    assert result.status_code == 403 and result.json()["code"] == "identity_read_only"


def test_last_accounts_self_lockout_and_root_bootstrap_are_protected(identities):
    app, login = identities
    hr = login()
    assert edit(hr, "local-hr", active=False).json()["code"] == "self_lockout"
    assert edit(hr, "local-admin", role="hr").json()["code"] == "bootstrap_protected"
    extra = create(hr, "extra.hr", "hr").json()["id"]
    another_hr = login("extra.hr")
    assert edit(another_hr, "local-hr", active=False).status_code == 200
    # A different administrator cannot remove the last local HR even when an external HR exists.
    assert edit(another_hr, extra, role="admin").json()["code"] == "self_lockout"


def test_search_pagination_and_response_never_reveal_passwords(identities):
    app, login = identities
    hr = login()
    assert create(hr, "search.operator").status_code == 201
    filtered = hr.get(
        "/api/v1/admin/users", params={"q": "SEARCH.OPERATOR", "limit": 1}
    ).json()
    assert filtered["total"] == 1 and len(filtered["items"]) == 1
    assert hr.get("/api/v1/admin/users", params={"q": "%"}).json()["total"] == 0
    assert hr.get("/api/v1/admin/users", params={"offset": 1, "limit": 1}).json()[
        "items"
    ]
    assert all(key not in str(filtered) for key in ["password", "$argon2", PASSWORD])


def test_identity_reads_allow_old_session_but_writes_require_recent_login(
    identities, store
):
    app, login = identities
    hr = login()
    with store.cs() as session:
        row = session.scalar(
            select(AuthSession).where(AuthSession.user_id == "local-hr")
        )
        row.expires_at = time.time() + 28800 - 901
    assert hr.get("/api/v1/admin/users").status_code == 200
    assert create(hr, "needs.reauth").status_code == 401


def test_concurrent_identity_edits_have_one_winner(identities):
    from concurrent.futures import ThreadPoolExecutor
    import threading

    app, login = identities
    initial = login().get("/api/v1/admin/users").json()["version"]
    barrier = threading.Barrier(2)

    def provision(index):
        client = login()
        barrier.wait(timeout=5)
        return create(
            client, f"concurrent.operator.{index}", version=initial
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(provision, [1, 2])) == [201, 409]

"""Catalog authoring, access isolation and historical competency snapshots."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from sqlalchemy import select
from app.models import Campaign, Skill, Audit, Team, RoleProfile, Publication
from app.services import (
    load_catalog,
    create_campaign,
    enqueue_generation,
    assignments,
    form,
    campaign_transition,
    seed_answers,
    start_run,
)
from app.worker import Worker
from app.providers import Provider
from app.reporting import publish
from app.store import DomainError
from test_access import scoped


def payload(code=70):
    return {
        "code": code,
        "name": "Agentic Workflow Design",
        "definition": "AI ajanları için doğrulanabilir ve kontrollü iş akışları tasarlar.",
        "levels": [
            {
                "level": n,
                "label": f"Seviye {n}",
                "description": f"Seviye {n} gözlemlenebilir davranış tanımı.",
            }
            for n in range(1, 6)
        ],
        "owners": ["Skill Owner"],
        "domain": "AI",
        "family": "Agents",
        "owner_department": "Platform",
        "expected_version": 1,
    }


def editable(row):
    return {key: row[key] for key in payload() if key != "expected_version"} | {
        "expected_version": row["version"]
    }


def test_catalog_lifecycle_paging_audit_and_bootstrap(client, store):
    value = payload()
    created = client.post("/api/v1/skills", json=value)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["id"] == "SKILL-070" and row["version"] == 1
    assert client.get("/api/v1/bootstrap").json()["skills_count"] == 43
    page = client.get(
        "/api/v1/catalog/skills", params={"q": "Agentic Workflow Design", "limit": 1}
    ).json()
    assert page["total"] == 1 and page["items"][0] == row and page["next_code"] == 71
    assert client.post("/api/v1/skills", json=value).status_code == 409
    changed = {**value, "name": "AI Agent Assurance"}
    assert (
        client.patch(
            "/api/v1/skills/SKILL-070", json={**changed, "code": 71}
        ).status_code
        == 409
    )
    changed_row = client.patch("/api/v1/skills/SKILL-070", json=changed).json()
    assert changed_row["version"] == 2
    assert client.patch("/api/v1/skills/SKILL-070", json=changed).status_code == 409
    assert (
        client.delete("/api/v1/skills/SKILL-070?expected_version=1").status_code == 409
    )
    removed = client.delete("/api/v1/skills/SKILL-070?expected_version=2").json()
    assert removed["archived"] and removed["version"] == 3
    assert client.get("/api/v1/bootstrap").json()["skills_count"] == 42
    assert "SKILL-070" not in {x["id"] for x in client.get("/api/v1/skills").json()}
    assert (
        len(client.get("/api/v1/skills?include_archived=true&compact=true").json())
        == 43
    )
    archived = client.get("/api/v1/catalog/skills?status=archived").json()
    assert archived["total"] == 1 and archived["items"][0]["name"] == changed["name"]
    assert (
        client.patch("/api/v1/skills/SKILL-070", json=editable(removed)).status_code
        == 409
    )
    assert (
        client.post("/api/v1/skills/SKILL-070/restore?expected_version=2").status_code
        == 409
    )
    restored = client.post("/api/v1/skills/SKILL-070/restore?expected_version=3").json()
    assert restored["version"] == 4 and not restored["archived"]
    assert (
        client.post("/api/v1/skills/SKILL-070/restore?expected_version=4").status_code
        == 409
    )
    load_catalog(store)
    with store.session() as s:
        assert s.get(Skill, row["id"]).name == changed["name"]
        records = list(s.scalars(select(Audit).where(Audit.entity_id == row["id"])))
        assert len(records) == 4 and all(
            x.detail["actor_id"] == "test-hr" for x in records
        )
        assert (
            next(x for x in records if x.action == "catalog_skill_updated").detail[
                "before"
            ]["name"]
            == value["name"]
        )


@pytest.mark.parametrize("invalid", ["levels", "blank", "code", "unknown", "owner"])
def test_catalog_input_validation(client, invalid):
    value = payload()
    if invalid == "levels":
        value["levels"][4]["level"] = 4
    if invalid == "blank":
        value["levels"][0]["description"] = "   "
    if invalid == "code":
        value["code"] = 10000
    if invalid == "unknown":
        value["archived"] = False
    if invalid == "owner":
        value["owners"] = ["   "]
    assert client.post("/api/v1/skills", json=value).status_code == 422


@pytest.mark.parametrize("role", ["e1", "m1", "ia"])
def test_catalog_mutations_hr_only(scoped, role):
    _, as_user = scoped
    with as_user(role) as c:
        for method, path, data in [
            ("POST", "/skills", payload()),
            ("PATCH", "/skills/SKILL-005", payload(5)),
            ("DELETE", "/skills/SKILL-005?expected_version=1", None),
            ("POST", "/skills/SKILL-005/restore?expected_version=1", None),
        ]:
            assert c.request(method, "/api/v1" + path, json=data).status_code == 403
        assert c.get("/api/v1/catalog/skills").status_code == (
            403 if role == "ia" else 200
        )


def test_common_competencies_protected_and_original_metadata_preserved(client, store):
    for code in [1, 2, 4]:
        assert (
            client.delete(
                f"/api/v1/skills/SKILL-{code:03}?expected_version=1"
            ).status_code
            == 409
        )
    row = client.get("/api/v1/skills").json()[0]
    with store.session() as s:
        original = deepcopy(s.get(Skill, row["id"]).metadata_)
    changed = editable(row) | {"name": "Yeni ortak yetkinlik adı"}
    assert client.patch("/api/v1/skills/" + row["id"], json=changed).status_code == 200
    with store.session() as s:
        assert all(
            s.get(Skill, row["id"]).metadata_[k] == v
            for k, v in original.items()
            if k not in {"owners", "domain", "family", "owner_department"}
        )


def test_legacy_and_new_periods_freeze_content_before_edit(client, store, monkeypatch):
    cid = create_campaign(store, "Legacy period", ["team-data"])["id"]
    with store.session() as s:
        period = s.get(Campaign, cid)
        period.config = {
            k: v for k, v in period.config.items() if k != "skill_snapshots"
        }
    row = next(x for x in client.get("/api/v1/skills").json() if x["id"] == "SKILL-005")
    updated = editable(row) | {
        "name": "Updated data skill",
        "definition": "Updated definition applies to future periods only.",
    }
    assert client.patch("/api/v1/skills/SKILL-005", json=updated).status_code == 200
    seen = []
    complete = Provider.complete

    def capture(self, purpose, data, *args, **kwargs):
        if purpose == "questions":
            seen.extend(data["skills"])
        return complete(self, purpose, data, *args, **kwargs)

    monkeypatch.setattr(Provider, "complete", capture)
    enqueue_generation(store, cid)
    Worker(store).drain()
    snapshot = next(x for x in seen if x["id"] == row["id"])
    assert (
        snapshot["name"] == row["name"]
        and snapshot["definition"] == row["definition"]
        and snapshot["levels"] == row["levels"]
    )
    campaign_transition(store, cid, "approve")
    campaign_transition(store, cid, "open")
    f = form(store, assignments(store, cid)[0]["id"])
    assert all(
        q["skill_name"] == row["name"]
        for q in f["questions"]
        if q["skill_id"] == row["id"]
    )
    new = create_campaign(store, "New period", ["team-data"])
    assert new["config"]["skill_snapshots"][row["id"]]["name"] == updated["name"]
    assert (
        client.delete("/api/v1/skills/SKILL-005?expected_version=2").status_code == 200
    )
    load_catalog(store)
    with pytest.raises(DomainError, match="Hedefleri"):
        create_campaign(store, "Invalid archived target", ["team-data"])
    enqueue_generation(store, new["id"])
    Worker(store).drain()
    with store.session() as s:
        assert s.get(Campaign, new["id"]).status == "content_review"
        assert s.get(Skill, row["id"]).metadata_["archived"]
    seed_answers(store, cid, 6)
    campaign_transition(store, cid, "close")
    run = start_run(store, cid)
    Worker(store).drain()
    from app.models import Run, Job

    with store.session() as s:
        assert s.get(Run, run["id"]).status == "ready_to_publish", [
            (j.kind, j.status, j.error) for j in s.scalars(select(Job))
        ]
    pid = publish(store, run["id"])
    with store.session() as s:
        report = deepcopy(s.get(Publication, pid).snapshot)
        assert all(
            r["skill_name"] == row["name"]
            for r in report["rows"]
            if r["skill_id"] == row["id"]
        )
    assert (
        client.post("/api/v1/skills/SKILL-005/restore?expected_version=3").status_code
        == 200
    )
    with store.session() as s:
        assert s.get(Publication, pid).snapshot == report


def test_custom_skill_usable_in_generated_forms(client, store):
    response = client.post("/api/v1/skills", json=payload())
    assert response.status_code == 201
    with store.session() as s:
        team = s.get(Team, "team-data")
        team.targets = [
            {**t, "skill_id": "SKILL-070"} if t["skill_id"] == "SKILL-005" else t
            for t in team.targets
        ]
        for role in s.scalars(
            select(RoleProfile).where(RoleProfile.team_id == team.id)
        ):
            role.targets = team.targets
    cid = create_campaign(store, "Custom skill period", ["team-data"])["id"]
    enqueue_generation(store, cid)
    Worker(store).drain()
    campaign_transition(store, cid, "approve")
    campaign_transition(store, cid, "open")
    questions = form(store, assignments(store, cid)[0]["id"])["questions"]
    assert len(questions) == 22
    assert any(
        q["skill_id"] == "SKILL-070" and q["skill_name"] == payload()["name"]
        for q in questions
    )


def test_catalog_version_prevents_concurrent_lost_updates(client, store):
    row = client.post("/api/v1/skills", json=payload()).json()

    def write(n):
        return client.patch(
            "/api/v1/skills/" + row["id"],
            json=editable(row) | {"name": f"Concurrent edit {n}"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, range(2))) == [200, 409]

"""HR draft authoring, versioned approval, frozen published sets and variable scoring."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest
from sqlalchemy import select
from app.models import Campaign, Question, Audit, Publication, Run, Assignment
from app.services import (
    create_campaign,
    enqueue_generation,
    campaign_transition,
    assignments,
    form,
    seed_answers,
    start_run,
)
from app.worker import Worker
from app.reporting import publish
from test_access import scoped


def prepared(store, teams=None):
    cid = create_campaign(store, "HR editable set", teams or ["team-data"])["id"]
    enqueue_generation(store, cid)
    Worker(store).drain()
    return cid


def view(c, cid):
    result = c.get(f"/api/v1/campaigns/{cid}/question-set")
    assert result.status_code == 200, result.text
    return result.json()


def payload(q, version):
    return {
        k: deepcopy(q[k])
        for k in (
            "form_key",
            "skill_id",
            "type",
            "prompt",
            "options",
            "rubric",
            "reference",
            "evidence_type",
        )
    } | {"expected_version": version}


def test_edit_add_remove_save_reload_then_approve_publish(client, store):
    cid = prepared(store)
    original = view(client, cid)
    q = next(q for q in original["questions"] if q["type"] == "open_text")
    body = payload(q, original["version"])
    body["prompt"] = (
        "İK tarafından düzenlenmiş senaryo: AI çıktısını nasıl doğrularsınız?"
    )
    body["rubric"][0][
        "descriptor"
    ] = "Özgün kaynak, bağımsız kontrol ve insan onayı açıklanmalı."
    changed = client.patch(f"/api/v1/campaigns/{cid}/questions/{q['id']}", json=body)
    assert changed.status_code == 200, changed.text
    data = changed.json()
    assert data["revision"] == 2 and data["version"] > original["version"]
    assert (
        next(x for x in view(client, cid)["questions"] if x["id"] == q["id"])["prompt"]
        == body["prompt"]
    )
    added = client.post(
        f"/api/v1/campaigns/{cid}/questions",
        json=payload(q, data["version"])
        | {"prompt": "İK ek sorusu: özgün kaynak doğrulamasına bir örnek verin."},
    )
    assert added.status_code == 201, added.text
    data = added.json()
    assert len(data["questions"]) == 23
    extra = next(x for x in data["questions"] if x["prompt"].startswith("İK ek sorusu"))
    removed = client.delete(
        f"/api/v1/campaigns/{cid}/questions/{extra['id']}",
        params={"expected_version": data["version"]},
    )
    assert removed.status_code == 200
    data = removed.json()
    assert len(data["questions"]) == 22 and not data["issues"]
    approved = client.post(
        f"/api/v1/campaigns/{cid}/approve", json={"expected_version": data["version"]}
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ready"
    assert not assignments(store, cid)
    assert approved.json()["config"]["question_approval"]["actor_id"] == "test-hr"
    opened = client.post(
        f"/api/v1/campaigns/{cid}/open",
        json={"expected_version": approved.json()["row_version"]},
    )
    assert opened.status_code == 200, opened.text
    employee_form = form(store, assignments(store, cid)[0]["id"])
    assert any(x["prompt"] == body["prompt"] for x in employee_form["questions"])
    assert all("rubric" not in x for x in employee_form["questions"])
    with store.session() as s:
        audits = list(s.scalars(select(Audit).where(Audit.entity_id == cid)))
        assert {
            "question_created",
            "question_updated",
            "question_deleted",
            "campaign_approve",
            "campaign_open",
        }.issubset({a.action for a in audits})
        assert (
            next(a for a in audits if a.action == "question_updated").detail["before"][
                "prompt"
            ]
            == q["prompt"]
        )


def test_ready_edit_invalidates_approval_and_stale_publish(client, store):
    cid = prepared(store)
    data = view(client, cid)
    approved = client.post(
        f"/api/v1/campaigns/{cid}/approve", json={"expected_version": data["version"]}
    ).json()
    data = view(client, cid)
    q = data["questions"][0]
    saved = client.patch(
        f"/api/v1/campaigns/{cid}/questions/{q['id']}",
        json=payload(q, data["version"])
        | {"prompt": "Onay sonrasında düzeltilen soru metni."},
    )
    assert saved.status_code == 200
    current = saved.json()
    assert current["status"] == "content_review" and current["approval"] is None
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/open",
            json={"expected_version": approved["row_version"]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/open",
            json={"expected_version": current["version"]},
        ).status_code
        == 409
    )
    assert not assignments(store, cid)


@pytest.mark.parametrize("role", ["m1", "e1", "ia"])
def test_only_hr_can_edit_approve_or_publish(scoped, store, role):
    _, as_user = scoped
    cid = prepared(store)
    with as_user("hr") as c:
        data = view(c, cid)
    q = data["questions"][0]
    with as_user(role) as c:
        for method, path, body in [
            ("POST", f"/campaigns/{cid}/questions", payload(q, data["version"])),
            (
                "PATCH",
                f"/campaigns/{cid}/questions/{q['id']}",
                payload(q, data["version"]),
            ),
            (
                "DELETE",
                f"/campaigns/{cid}/questions/{q['id']}?expected_version={data['version']}",
                None,
            ),
            (
                "POST",
                f"/campaigns/{cid}/approve",
                {"expected_version": data["version"]},
            ),
            ("POST", f"/campaigns/{cid}/open", {"expected_version": data["version"]}),
        ]:
            assert c.request(method, "/api/v1" + path, json=body).status_code == 403
        read = c.get(f"/api/v1/campaigns/{cid}/question-set")
        assert (
            read.status_code == 403
        )  # m1 only owns a subset of this entire-team period.


def test_missing_coverage_can_be_saved_but_not_published(client, store):
    cid = prepared(store)
    data = view(client, cid)
    q = next(q for q in data["questions"] if q["type"] == "self_assessment")
    saved = client.delete(
        f"/api/v1/campaigns/{cid}/questions/{q['id']}",
        params={"expected_version": data["version"]},
    )
    assert saved.status_code == 200 and saved.json()["issues"]
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/approve",
            json={"expected_version": saved.json()["version"]},
        ).status_code
        == 409
    )
    restored = client.post(
        f"/api/v1/campaigns/{cid}/questions", json=payload(q, saved.json()["version"])
    )
    assert restored.status_code == 201 and not restored.json()["issues"]


@pytest.mark.parametrize(
    "invalid",
    ["blank", "foreign_group", "foreign_skill", "rubric", "options", "self_options"],
)
def test_question_semantics_reject_bad_input(client, store, invalid):
    cid = prepared(store)
    data = view(client, cid)
    kind = (
        "self_assessment"
        if invalid == "self_options"
        else "single_choice" if invalid == "options" else "open_text"
    )
    q = next(q for q in data["questions"] if q["type"] == kind)
    body = payload(q, data["version"])
    if invalid == "blank":
        body["prompt"] = "   "
    if invalid == "foreign_group":
        body["form_key"] = "another-period-role"
    if invalid == "foreign_skill":
        body["skill_id"] = "SKILL-042"
    if invalid == "rubric":
        body["rubric"][0]["anchors"] = {"0": "Empty"}
    if invalid == "options":
        body["options"][0]["correct"] = True
    if invalid == "self_options":
        body["options"].pop()
    response = client.post(f"/api/v1/campaigns/{cid}/questions", json=body)
    assert response.status_code in {400, 422}, response.text
    assert view(client, cid)["version"] == data["version"]


def test_cross_campaign_id_rejected_and_published_set_frozen(client, store):
    cid = prepared(store)
    second = prepared(store)
    data = view(client, cid)
    foreign = view(client, second)["questions"][0]
    assert (
        client.patch(
            f"/api/v1/campaigns/{cid}/questions/{foreign['id']}",
            json=payload(data["questions"][0], data["version"]),
        ).status_code
        == 404
    )
    campaign_transition(store, cid, "approve")
    campaign_transition(store, cid, "open")
    frozen = view(client, cid)
    body = payload(frozen["questions"][0], frozen["version"])
    assert not frozen["can_edit"]
    assert (
        client.patch(
            f"/api/v1/campaigns/{cid}/questions/{body.get('id', data['questions'][0]['id'])}",
            json=body,
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/v1/campaigns/{cid}/questions", json=body).status_code == 409
    )
    assert (
        client.delete(
            f"/api/v1/campaigns/{cid}/questions/{data['questions'][0]['id']}",
            params={"expected_version": frozen["version"]},
        ).status_code
        == 409
    )


def test_two_hr_edits_cannot_overwrite_same_version(client, store):
    cid = prepared(store)
    data = view(client, cid)
    q = data["questions"][0]

    def update(n):
        return client.patch(
            f"/api/v1/campaigns/{cid}/questions/{q['id']}",
            json=payload(q, data["version"]) | {"prompt": f"Concurrent HR edit {n}"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, range(2))) == [200, 409]


def test_added_and_removed_written_questions_score_using_actual_assigned_count(
    client, store
):
    cid = prepared(store, ["team-data", "team-software"])
    data = view(client, cid)
    common = next(
        q
        for q in data["questions"]
        if q["type"] == "open_text" and q["form_key"] == "common"
    )
    added = client.post(
        f"/api/v1/campaigns/{cid}/questions",
        json=payload(common, data["version"])
        | {
            "prompt": "Ek ortak senaryo: kaynakları ve insan onayını nasıl yönetirsiniz?"
        },
    )
    assert added.status_code == 201
    data = added.json()
    role = next(
        q
        for q in data["questions"]
        if q["type"] == "open_text" and q["form_key"] != "common"
    )
    deleted = client.delete(
        f"/api/v1/campaigns/{cid}/questions/{role['id']}",
        params={"expected_version": data["version"]},
    )
    assert deleted.status_code == 200 and not deleted.json()["issues"]
    approved = client.post(
        f"/api/v1/campaigns/{cid}/approve",
        json={"expected_version": deleted.json()["version"]},
    ).json()
    assert set(approved["config"]["question_counts"].values()) == {22, 23}
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/open",
            json={"expected_version": approved["row_version"]},
        ).status_code
        == 200
    )
    forms = [form(store, a["id"]) for a in assignments(store, cid)]
    assert {len(f["questions"]) for f in forms} == {22, 23}
    assert all(
        any(q["prompt"].startswith("Ek ortak senaryo") for q in f["questions"])
        for f in forms
    )
    seed_answers(store, cid, 20)
    campaign_transition(store, cid, "close")
    run = start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        assert s.get(Run, run["id"]).status == "ready_to_publish"
    pid = publish(store, run["id"])
    with store.session() as s:
        snap = s.get(Publication, pid).snapshot
        rows = snap["rows"]
        assert all(
            r["expected_written_questions"] == 3
            and r["coverage"] == 1
            and r["written_score"] is not None
            for r in rows
            if r["skill_id"] == common["skill_id"]
        )
        single = [
            r
            for r in rows
            if r["skill_id"] == role["skill_id"] and r["team_id"] == "team-data"
        ]
        assert single and all(
            r["expected_written_questions"] == 1
            and r["coverage"] == 1
            and r["written_score"] is not None
            and r["suggested_level"] is None
            for r in single
        )
        assert snap["question_approval"]["actor_id"] == "test-hr"


@pytest.mark.parametrize("transition", ["approve", "open"])
def test_publish_and_edit_race_never_changes_a_published_form(
    client, store, transition
):
    cid = prepared(store)
    if transition == "open":
        campaign_transition(store, cid, "approve")
    data = view(client, cid)
    q = data["questions"][0]

    def execute(kind):
        if kind == "edit":
            return client.patch(
                f"/api/v1/campaigns/{cid}/questions/{q['id']}",
                json=payload(q, data["version"])
                | {"prompt": "Concurrent publish correction"},
            ).status_code
        return client.post(
            f"/api/v1/campaigns/{cid}/{transition}",
            json={"expected_version": data["version"]},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(execute, ["edit", "transition"])) == [200, 409]
    current = view(client, cid)
    if current["status"] == "open":
        assert (
            next(x for x in current["questions"] if x["id"] == q["id"])["prompt"]
            == q["prompt"]
        )


def test_question_authoring_never_calls_llm(client, store, monkeypatch):
    cid = prepared(store)
    data = view(client, cid)
    from app.providers import Provider

    def denied(*args, **kwargs):
        raise AssertionError("Authoring must not call LLM")

    monkeypatch.setattr(Provider, "complete", denied)
    q = data["questions"][0]
    saved = client.patch(
        f"/api/v1/campaigns/{cid}/questions/{q['id']}",
        json=payload(q, data["version"]) | {"prompt": "HR-authored question text"},
    )
    assert saved.status_code == 200
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/approve",
            json={"expected_version": saved.json()["version"]},
        ).status_code
        == 200
    )

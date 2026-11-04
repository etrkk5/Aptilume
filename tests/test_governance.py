"""HR instructions and post-campaign quality triage use normal audited access paths."""

import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import Settings
from app.models import (
    Assignment,
    Campaign,
    Evaluation,
    Job,
    PromptPolicy,
    Publication,
    QualityIssue,
    Run,
    RunPolicy,
)
from app.policies import default_instructions, policy
from app.providers import Provider, GradeOutput
from app.quality import local_quality
from app.reporting import publish
from app.services import (
    create_campaign,
    enqueue_generation,
    campaign_transition,
    assignments,
    form,
    save_answer,
    submit,
    start_run,
)
from app.store import Store, DomainError
from app.worker import Worker
from test_access import scoped, open_campaign


def answer_form(
    store,
    aid,
    first="Kaynakları ve varsayımları kontrol ederim. Çıktıyı bağımsız kanıtlarla doğrular, riskleri ve insan onayını kaydederim.",
):
    questions = form(store, aid)["questions"]
    first_open = True
    for q in questions:
        if q["type"] == "open_text":
            text = (
                first
                if first_open
                else "Kaynakları kontrol eder, çıktıyı karşılaştırır ve riskli kararları insan onayına sunarım."
            )
            first_open = False
            value = {"text": text, "revision": 0}
        else:
            value = {
                "selected": ["none" if q["type"] == "self_assessment" else "b"],
                "revision": 0,
            }
        save_answer(store, aid, q["id"], value)
    return submit(store, aid)


@pytest.fixture
def quality_run(store):
    cid = open_campaign(store)
    aid = next(
        a["id"]
        for a in assignments(store, cid)
        if a["participant_id"] == "team-data-person-03"
    )
    answer_form(store, aid, "asdfasdf")
    with store.session() as s:
        assert not list(s.scalars(select(QualityIssue)))
        assert not list(s.scalars(select(Evaluation)))
    campaign_transition(store, cid, "close")
    run = start_run(store, cid)
    Worker(store).drain()
    return cid, run["id"], aid


def test_required_form_rejects_blank_invisible_and_unselected_questions(store):
    cid = open_campaign(store)
    aid = assignments(store, cid)[0]["id"]
    with pytest.raises(DomainError) as error:
        submit(store, aid)
    assert error.value.code == "incomplete_form"
    q = next(q for q in form(store, aid)["questions"] if q["type"] == "open_text")
    save_answer(store, aid, q["id"], {"text": "\u200b\ufeff", "revision": 0})
    with pytest.raises(DomainError):
        submit(store, aid)
    with store.session() as s:
        assert not list(s.scalars(select(QualityIssue)))


def test_quality_is_only_computed_post_campaign_and_blocks_publication(
    store, quality_run
):
    _, rid, _ = quality_run
    with store.session() as s:
        assert s.get(Run, rid).status == "review_required"
        issues = list(s.scalars(select(QualityIssue)))
        assert issues and all(i.category == "nonsensical" for i in issues)
        for issue in issues:
            e = s.get(Evaluation, issue.evaluation_id)
            assert (
                e.score is None
                and e.status == "unscorable"
                and e.review_status == "pending"
            )
    with pytest.raises(DomainError):
        publish(store, rid)


def test_only_hr_receives_and_resolves_quality_cases(store, scoped, quality_run):
    _, rid, _ = quality_run
    _, as_user = scoped
    with as_user("hr") as client:
        response = client.get("/api/v1/quality-cases")
        assert response.status_code == 200
        body = response.json()
        issue = body["items"][0]
        assert body["summary"]["people"] == 1 and body["summary"]["pending"] >= 1
        assert (
            client.get("/api/v1/bootstrap").json()["quality_pending"]
            == body["summary"]["pending"]
        )
        assert (
            client.get(
                "/api/v1/quality-cases", params={"team_id": "team-software"}
            ).json()["total"]
            == 0
        )
        detail = client.get("/api/v1/quality-cases/" + issue["id"]).json()
        assert detail["answer"] == "asdfasdf" and detail["can_review"]
        assert (
            client.post(
                f"/api/v1/reviews/{issue['evaluation_id']}/decision",
                json={"reason": "Gerekçeli İK incelemesi", "score": None},
            ).status_code
            == 400
        )
    for role in ["m1", "e1", "ia"]:
        with as_user(role) as client:
            assert client.get("/api/v1/quality-cases").status_code == 403
            assert client.get("/api/v1/quality-cases/" + issue["id"]).status_code == 403
            assert (
                client.post(
                    f"/api/v1/reviews/{issue['evaluation_id']}/decision",
                    json={"reason": "Yetkisiz inceleme denemesi", "score": 0},
                ).status_code
                == 403
            )
    with as_user("hr") as client:
        for item in client.get("/api/v1/quality-cases").json()["items"]:
            url = f"/api/v1/reviews/{item['evaluation_id']}/decision"
            assert (
                client.post(
                    url,
                    json={
                        "reason": "Yanıtta değerlendirilebilir kanıt bulunmadı.",
                        "score": 0,
                    },
                ).status_code
                == 200
            )
            assert (
                client.post(
                    url, json={"reason": "Tekrar karar denemesi.", "score": 0}
                ).status_code
                == 409
            )
        assert client.get("/api/v1/quality-cases").json()["summary"]["pending"] == 0
    Worker(store).drain()
    pub = publish(store, rid)
    with store.session() as s:
        assert s.get(Publication, pub).snapshot["rows"]


def test_honest_no_experience_is_not_a_quality_violation(store):
    cid = open_campaign(store)
    aid = assignments(store, cid)[0]["id"]
    answer_form(store, aid, "Deneyimim yok.")
    campaign_transition(store, cid, "close")
    rid = start_run(store, cid)["id"]
    Worker(store).drain()
    with store.session() as s:
        assert not list(s.scalars(select(QualityIssue)))
        assert s.get(Run, rid).status == "ready_to_publish"


@pytest.mark.parametrize(
    "value", [";;;;", "😀😀😀", "aaaaaaa", "asdf asdf", "qwerty", "lorem ipsum"]
)
def test_obvious_nonanswers_are_provisional_quality_flags(value):
    assert local_quality(value) == "nonsensical"


@pytest.mark.parametrize(
    "value", ["Kaynağı kontrol ederim.", "Bilmiyorum", "Bu konuda deneyimim yok."]
)
def test_short_or_honest_answers_are_not_labelled_nonsense(value):
    assert local_quality(value) in (None, "no_experience")


def test_model_can_flag_semantic_irrelevance_and_case_keeps_exact_evidence(
    store, monkeypatch
):
    original = Provider.complete

    def answer(self, task, payload, schema=None, instructions=None):
        raw, usage = original(self, task, payload, schema, instructions)
        if task == "grade" and payload["answer"].startswith("Bugün"):
            raw["quality"] = {
                "category": "off_topic",
                "reason": "Yanıt soru yerine yemek tercihinden söz ediyor.",
                "evidence_quotes": ["Bugün pizza yedim."],
            }
        return raw, usage

    monkeypatch.setattr(Provider, "complete", answer)
    cid = open_campaign(store)
    aid = assignments(store, cid)[0]["id"]
    answer_form(store, aid, "Bugün pizza yedim.")
    campaign_transition(store, cid, "close")
    start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        issue = s.scalar(select(QualityIssue))
        assert issue.category == "off_topic" and issue.evidence_quotes == [
            "Bugün pizza yedim."
        ]
        assert s.get(Evaluation, issue.evaluation_id).score is None


def test_policy_defaults_and_edits_are_hr_only_and_versioned(store, scoped):
    _, as_user = scoped
    with as_user("hr") as client:
        data = client.get("/api/v1/prompt-policies").json()
        assert data["active"]["instructions"] == default_instructions()
        value = {
            "expected_version": 1,
            "instructions": {
                **data["active"]["instructions"],
                "questions": data["active"]["instructions"]["questions"]
                + " Additional HR policy.",
            },
        }
        saved = client.post("/api/v1/prompt-policies", json=value)
        assert saved.status_code == 201 and saved.json()["version"] == 2
        assert client.post("/api/v1/prompt-policies", json=value).status_code == 409
        assert (
            client.get("/api/v1/prompt-policies/default-v1").json()["instructions"]
            == default_instructions()
        )
    for role in ["m1", "e1", "ia"]:
        with as_user(role) as client:
            assert client.get("/api/v1/prompt-policies").status_code == 403
            assert client.post("/api/v1/prompt-policies", json=value).status_code == 403


@pytest.mark.parametrize("demo", [True, False])
def test_same_default_instructions_exist_in_development_and_production(tmp_path, demo):
    p = tmp_path / "runtime"
    store = Store(
        Settings(
            p,
            f"sqlite:///{p/'control.db'}",
            secret_key=Fernet.generate_key().decode(),
            demo=demo,
        )
    )
    assert policy(store)["instructions"] == default_instructions()


def test_background_jobs_pin_policy_even_after_hr_edits(store, client, monkeypatch):
    original = Provider.complete
    seen = []

    def capture(self, task, payload, schema=None, instructions=None):
        seen.append((task, instructions))
        return original(self, task, payload, schema, instructions)

    monkeypatch.setattr(Provider, "complete", capture)
    cid = create_campaign(store, "Policy test", ["team-data"])["id"]
    job = enqueue_generation(store, cid)
    assert job["payload"]["prompt_policy_id"] == "default-v1"
    defaults = default_instructions()
    second = {k: v + " HR policy version two." for k, v in defaults.items()}
    assert (
        client.post(
            "/api/v1/prompt-policies",
            json={"expected_version": 1, "instructions": second},
        ).status_code
        == 201
    )
    Worker(store).drain()
    assert all(
        text == defaults["questions"] for task, text in seen if task == "questions"
    )
    campaign_transition(store, cid, "approve")
    campaign_transition(store, cid, "open")
    answer_form(store, assignments(store, cid)[0]["id"])
    campaign_transition(store, cid, "close")
    rid = start_run(store, cid)["id"]
    third = {k: v + " HR policy version three." for k, v in defaults.items()}
    assert (
        client.post(
            "/api/v1/prompt-policies",
            json={"expected_version": 2, "instructions": third},
        ).status_code
        == 201
    )
    Worker(store).drain()
    assert all(text == second["grade"] for task, text in seen if task == "grade")
    assert all(text == second["insights"] for task, text in seen if task == "insights")
    with store.session() as s:
        assert s.get(RunPolicy, rid).version == 2
    pid = publish(store, rid)
    with store.session() as s:
        trace = s.get(Publication, pid).snapshot["prompt_policy"]
        assert trace["generation_version"] == 1 and trace["evaluation_version"] == 2


def test_concurrent_policy_save_does_not_lose_another_hr_edit(store, client):
    value = {"expected_version": 1, "instructions": default_instructions()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda _: client.post(
                    "/api/v1/prompt-policies", json=value
                ).status_code,
                range(2),
            )
        )
    assert sorted(statuses) == [201, 409]
    with store.cs() as s:
        assert len(list(s.scalars(select(PromptPolicy)))) == 2


def test_hr_cannot_resolve_their_own_quality_case(store, scoped, quality_run):
    from app.models import DirectoryUser

    with store.cs() as s:
        s.get(DirectoryUser, "hr").participant_id = "team-data-person-03"
    _, as_user = scoped
    with as_user("hr") as client:
        case = client.get("/api/v1/quality-cases").json()["items"][0]
        detail = client.get("/api/v1/quality-cases/" + case["id"]).json()
        assert detail["self_review"] and not detail["can_review"]
        response = client.post(
            f"/api/v1/reviews/{case['evaluation_id']}/decision",
            json={"score": 0, "reason": "Kendi yanıtım için karar."},
        )
        assert response.status_code == 403


def test_invalid_quality_evidence_is_not_presented_as_an_exact_quote(
    store, monkeypatch
):
    original = Provider.complete

    def wrong_quote(self, task, payload, schema=None, instructions=None):
        raw, usage = original(self, task, payload, schema, instructions)
        if task == "grade":
            raw["quality"] = {
                "category": "off_topic",
                "reason": "Model ön incelemesi.",
                "evidence_quotes": ["Yanıtta bulunmayan alıntı."],
            }
        return raw, usage

    monkeypatch.setattr(Provider, "complete", wrong_quote)
    cid = open_campaign(store)
    aid = assignments(store, cid)[0]["id"]
    answer_form(store, aid)
    campaign_transition(store, cid, "close")
    start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        issues = list(s.scalars(select(QualityIssue)))
        assert issues and all(i.evidence_quotes == [] for i in issues)
        assert all(
            "unsupported_quality_quote" in s.get(Evaluation, i.evaluation_id).flags
            for i in issues
        )
        assert all(s.get(Evaluation, i.evaluation_id).score is None for i in issues)

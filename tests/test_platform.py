import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from openpyxl import load_workbook
from sqlalchemy import select, update
from app.models import *
from app.services import *
from app.reporting import build_snapshot, metrics, publish
from app.providers import Provider, validate_grade
from app.worker import Worker
from app.store import DomainError, Store
from app.config import Settings


def prepared(store):
    c = create_campaign(store, "Test campaign", ["team-data"])
    enqueue_generation(store, c["id"])
    Worker(store).drain()
    campaign_transition(store, c["id"], "approve")
    campaign_transition(store, c["id"], "open")
    return c["id"]


def completed(store, count=6):
    cid = prepared(store)
    seed_answers(store, cid, count)
    campaign_transition(store, cid, "close")
    r = start_run(store, cid)
    Worker(store).drain()
    return cid, r["id"]


def test_catalog_idempotent_and_conflicting_ids(store):
    info = load_catalog(store)
    with store.session() as s:
        assert len(list(s.scalars(select(Skill)))) == 42
        skill = s.get(Skill, "SKILL-005")
        assert "Veri Analizi" in skill.name
        assert sum(len(x.levels) for x in s.scalars(select(Skill))) == 210
    assert info["skills"] == 42


def test_mixed_form_is_frozen_and_hides_keys(store):
    cid = prepared(store)
    a = assignments(store, cid)[0]
    f = form(store, a["id"])
    assert len(f["questions"]) == 22
    assert sum(q["type"] == "open_text" for q in f["questions"]) == 12
    assert all(
        "rubric" not in q and all("correct" not in o for o in q["options"])
        for q in f["questions"]
    )


def test_draft_persists_and_rejects_stale_revision(store):
    cid = prepared(store)
    a = assignments(store, cid)[0]
    q = form(store, a["id"])["questions"][0]
    save_answer(
        store,
        a["id"],
        q["id"],
        {"text": "Veriyi özgün kaynakla doğrularım.", "revision": 0},
    )
    reopened = Store(store.settings)
    assert form(reopened, a["id"])["questions"][0]["answer"]["text"].startswith(
        "Veriyi"
    )
    with pytest.raises(DomainError, match="başka bir sekmede"):
        save_answer(store, a["id"], q["id"], {"text": "Eski kayıt", "revision": 0})


def test_submit_never_calls_llm_and_open_evaluation_rejected(store):
    cid = prepared(store)
    seed_answers(store, cid, 1)
    with store.session() as s:
        assert len(list(s.scalars(select(Call)))) == 0
    with pytest.raises(DomainError):
        start_run(store, cid)
    a = assignments(store, cid)[0]
    assert submit(store, a["id"])["status"] == "submitted"


def test_closed_campaign_rejects_edits(store):
    cid = prepared(store)
    a = assignments(store, cid)[0]
    q = form(store, a["id"])["questions"][0]
    campaign_transition(store, cid, "close")
    with pytest.raises(DomainError):
        save_answer(store, a["id"], q["id"], {"text": "Yeni kayıt", "revision": 0})


def test_answer_type_and_option_validation(store):
    cid = prepared(store)
    a = assignments(store, cid)[0]
    qs = form(store, a["id"])["questions"]
    mc = next(q for q in qs if q["type"] == "single_choice")
    with pytest.raises(DomainError):
        save_answer(store, a["id"], mc["id"], {"selected": ["invented"], "revision": 0})
    with pytest.raises(DomainError):
        submit(store, a["id"])


def test_scoring_math_quotes_and_missing_schema():
    rub = [{"id": x, "weight": 1} for x in ["a", "b", "c"]]
    raw = {
        "status": "scored",
        "criteria": [
            {
                "criterion_id": k,
                "points": p,
                "evidence_quotes": ["kanıt"],
                "reason": "gerekçe",
                "missing_elements": [],
            }
            for k, p in zip(["a", "b", "c"], [4, 3, 1])
        ],
        "evidence_type": "scenario_reasoning",
        "review_flags": [],
        "limitations": [],
        "quality": {
            "category": "relevant",
            "reason": "Soruya ilişkin yanıt.",
            "evidence_quotes": [],
        },
    }
    _, score, flags = validate_grade(raw, "kanıt burada", rub)
    assert score == pytest.approx(100 * 8 / 12) and flags == []
    raw["criteria"][0]["evidence_quotes"] = ["uydurma"]
    assert "unsupported_quote" in validate_grade(raw, "kanıt burada", rub)[2]
    raw["criteria"].pop()
    with pytest.raises(DomainError):
        validate_grade(raw, "kanıt", rub)


def test_batch_idempotence_snapshot_and_publication(store):
    cid, rid = completed(store)
    with store.session() as s:
        run = s.get(Run, rid)
        assert run.status == "ready_to_publish"
        manifest = run.input_manifest.copy()
        before = len(list(s.scalars(select(Evaluation))))
    assert Worker(store).drain() == 0
    pid = publish(store, rid)
    assert publish(store, rid) == pid
    with store.session() as s:
        assert len(list(s.scalars(select(Evaluation)))) == before
        snap = s.get(Publication, pid).snapshot
        assert (
            snap["input_hash"]
            == hashlib.sha256(json.dumps(manifest).encode()).hexdigest()
        )
        report = metrics(snap)
        assert report["assigned"] == 10 and report["submitted"] == 6
        assert report["completion_rate"] == 60 and len(report["rows"]) == 36
        assert all(x["validated_level"] is None for x in report["rows"])


def test_leases_claim_one_and_recover(store):
    cid = prepared(store)
    seed_answers(store, cid, 1)
    campaign_transition(store, cid, "close")
    start_run(store, cid)
    w1, w2 = Worker(store), Worker(store)
    j1 = w1.claim()
    j2 = w2.claim()
    assert j1.id != j2.id
    with store.session() as s:
        s.execute(update(Job).where(Job.id == j1.id).values(lease_until=0))
    j3 = w2.claim()
    assert j3.id == j1.id and j3.attempts == 2


def test_two_worker_threads_no_duplicate_results(store):
    cid = prepared(store)
    seed_answers(store, cid, 2)
    campaign_transition(store, cid, "close")
    r = start_run(store, cid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: Worker(store).drain(), range(2)))
    Worker(store).drain()
    with store.session() as s:
        evals = list(s.scalars(select(Evaluation)))
        assert len({(x.run_id, x.answer_id, x.pass_no) for x in evals}) == len(evals)
        assert s.get(Run, r["id"]).status == "ready_to_publish"


def test_mock_error_does_not_become_zero(store):
    p = store.save_profile(
        "llm",
        "Broken mock",
        {"provider": "mock", "model": "fixture", "scenario": "unauthorized"},
    )
    store.bind("evaluation", p["id"])
    cid = prepared(store)
    seed_answers(store, cid, 1)
    campaign_transition(store, cid, "close")
    r = start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        assert s.get(Run, r["id"]).status == "failed"
        assert not list(s.scalars(select(Evaluation)))
    with pytest.raises(DomainError):
        publish(store, r["id"])


def test_profile_version_secret_and_active_deletion(store):
    p = store.save_profile(
        "llm", "Secret profile", {"provider": "mock", "model": "v1"}, "hidden-key"
    )
    assert p["has_secret"] and "hidden-key" not in json.dumps(store.profiles())
    store.bind("evaluation", p["id"])
    with pytest.raises(DomainError):
        store.delete_profile(p["id"])
    store.save_profile(
        "llm", "New name", {"provider": "mock", "model": "v2"}, profile_id=p["id"]
    )
    assert store.resolve("evaluation")["model"] == "v1"
    assert store.resolve(version_id=p["id"] + ":2")["secret"] == "hidden-key"


def test_connectivity_simulation_label_and_safe_key(client):
    p = client.post(
        "/api/v1/admin/connections/llm",
        json={
            "name": "Test",
            "config": {"provider": "mock", "model": "test"},
            "secret": "never-leak",
        },
    ).json()
    assert "never-leak" not in json.dumps(p)
    r = client.post(f"/api/v1/admin/connections/llm/{p['id']}/test").json()
    assert r["mode"] == "mock" and r["message"] == "Simülasyon başarılı"


def test_http_adapter_request_and_response_without_network():
    requests = []

    def handler(req):
        requests.append(req)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": '{"ok":true}'}}
                ],
                "usage": {"total_tokens": 3},
            },
        )

    cfg = {
        "provider": "openai_compatible_chat",
        "endpoint": "https://llm.example/v1",
        "model": "test-model",
        "secret": "example-key",
    }
    p = Provider(cfg, "llm.example", httpx.MockTransport(handler))
    out, usage = p.complete("test", {})
    assert out == {"ok": True} and str(requests[0].url).endswith("/v1/chat/completions")
    assert requests[0].headers["authorization"] == "Bearer example-key"
    assert json.loads(requests[0].content)["model"] == "test-model"


def test_endpoint_allowlist_and_metadata_denied():
    with pytest.raises(DomainError):
        Provider(
            {
                "provider": "openai_responses",
                "endpoint": "http://169.254.169.254",
                "model": "x",
            },
            "169.254.169.254",
        ).complete("test", {})
    with pytest.raises(DomainError):
        Provider(
            {
                "provider": "openai_responses",
                "endpoint": "https://not-allowed.example",
                "model": "x",
            }
        ).complete("test", {})


def test_export_snapshot_and_formula_safety(store):
    cid, rid = completed(store)
    with store.session() as s:
        # Freeze an intentionally formula-looking submitted value into the publication fixture.
        run = s.get(Run, rid)
        answer = s.get(Answer, run.input_manifest[0])
        answer.text = '=HYPERLINK("https://example.invalid","click")'
    pid = publish(store, rid)
    from app.exports import build_export

    for detail in [False, True]:
        with store.session() as s:
            e = Export(publication_id=pid, filters={}, detail=detail)
            s.add(e)
            s.flush()
            eid = e.id
        build_export(store, eid)
        with store.session() as s:
            file = s.get(Export, eid).file
        wb = load_workbook(file, data_only=False)
        assert ("Yanitlar" in wb.sheetnames) == detail
        assert not any(c.data_type == "f" for ws in wb for row in ws for c in row)
        summary = {r[0].value: r[1].value for r in wb["Ozet"].iter_rows(min_row=2)}
        assert summary["publication_id"] == pid and summary["submitted"] == 6


def test_small_group_and_missing_results_not_zero(store):
    cid, rid = completed(store, 2)
    with store.session() as s:
        report = metrics(build_snapshot(s, rid))
    assert report["common_score"] is None
    assert all(
        x["suppressed"] and x["written_score"] is None for x in report["aggregates"]
    )


def test_db_test_does_not_create_domain_tables(client, store):
    path = store.settings.data_dir / "new-empty.db"
    p = client.post(
        "/api/v1/admin/connections/db",
        json={"name": "New SQLite", "config": {"engine": "sqlite", "path": str(path)}},
    ).json()
    assert (
        client.post(f"/api/v1/admin/connections/db/{p['id']}/test").json()["status"]
        == "success"
    )
    from sqlalchemy import inspect
    from app.store import engine_for

    e = engine_for(f"sqlite:///{path}")
    assert inspect(e).get_table_names() == []


def test_sqlite_migration_preserves_data(store):
    p = store.save_profile(
        "db",
        "Next DB",
        {"engine": "sqlite", "path": str(store.settings.data_dir / "next.db")},
    )
    result = store.activate_db(p["id"])
    assert result["counts"]["skills"] == 42
    with store.session() as s:
        assert len(list(s.scalars(select(Participant)))) == 30


def test_health_and_unknown_endpoint(client):
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/application").status_code == 200
    assert client.get("/api/v1/nonexistent").status_code == 404


def test_multiple_titles_within_one_team_have_distinct_role_forms(store, client):
    seed_roles(store)
    original = store.settings.data_dir
    targets = [
        {"skill_id": sid, "target_level": 4, "criticality": 5, "applicable": True}
        for sid in COMMON + ["SKILL-032", "SKILL-033", "SKILL-034"]
    ]
    role = client.post(
        "/api/v1/role-profiles",
        json={
            "team_id": "team-data",
            "title": "Analytics Lead",
            "job_band": "L5_L6",
            "targets": targets,
        },
    ).json()
    assert role.get("id")
    p = client.post(
        "/api/v1/participants",
        json={
            "name": "Demo Lead",
            "title": "Senior Analytics Lead",
            "role_profile_id": role["id"],
            "job_band": "L5_L6",
        },
    ).json()
    cid = prepared(store)
    rows = assignments(store, cid)
    lead = next(x for x in rows if x["participant_id"] == p["id"])
    standard = next(x for x in rows if x["participant_id"] != p["id"])
    lead_form = form(store, lead["id"])
    standard_form = form(store, standard["id"])
    assert len(lead_form["questions"]) == 22
    assert {q["id"] for q in lead_form["questions"] if q["section"] == "common"} == {
        q["id"] for q in standard_form["questions"] if q["section"] == "common"
    }
    assert {
        q["id"] for q in lead_form["questions"] if q["section"] == "role"
    }.isdisjoint(
        {q["id"] for q in standard_form["questions"] if q["section"] == "role"}
    )
    assert any(q["skill_id"] == "SKILL-033" for q in lead_form["questions"])
    assert lead["profile_snapshot"]["role_profile"]["targets"][0]["target_level"] == 4


@pytest.mark.parametrize(
    "scenario,expected_attempts",
    [("timeout", 3), ("rate_limit", 3), ("server_error", 3), ("invalid_json", 2)],
)
def test_mock_failures_are_bounded_and_never_score_zero(
    store, scenario, expected_attempts
):
    p = store.save_profile(
        "llm",
        "Fault fixture",
        {"provider": "mock", "model": "fixture", "scenario": scenario},
    )
    store.bind("evaluation", p["id"])
    cid = prepared(store)
    seed_answers(store, cid, 1)
    campaign_transition(store, cid, "close")
    r = start_run(store, cid)
    w = Worker(store)
    for _ in range(expected_attempts + 1):
        w.drain()
        with store.session() as s:
            s.execute(
                update(Job)
                .where(Job.run_id == r["id"], Job.status == "queued")
                .values(available_at=0)
            )
    with store.session() as s:
        jobs = list(s.scalars(select(Job).where(Job.run_id == r["id"])))
        assert all(
            j.attempts == expected_attempts and j.status == "failed" for j in jobs
        )
        assert not list(s.scalars(select(Evaluation)))


def test_profile_edit_can_activate_new_version(store):
    p = store.save_profile("llm", "First", {"provider": "mock", "model": "first"})
    store.bind("evaluation", p["id"])
    updated = store.save_profile(
        "llm", "Second", {"provider": "mock", "model": "second"}, profile_id=p["id"]
    )
    assert (
        "evaluation" in updated["outdated_bindings"]
        and "evaluation" not in updated["active_for"]
    )
    store.bind("evaluation", p["id"])
    assert store.resolve("evaluation")["model"] == "second"


def test_postgres_engine_accepts_structured_url():
    from sqlalchemy.engine import URL
    from app.store import engine_for

    engine = engine_for(
        URL.create(
            "postgresql+psycopg",
            username="fixture",
            host="example.invalid",
            database="fixture",
        )
    )
    assert engine.url.get_backend_name() == "postgresql"
    engine.dispose()


def test_unmeasured_senior_target_never_becomes_a_skill_gap(store):
    cid = prepared(store)
    with store.session() as s:
        for a in s.scalars(select(Assignment).where(Assignment.campaign_id == cid)):
            snap = json.loads(json.dumps(a.profile_snapshot))
            for target in snap["team"]["targets"]:
                target["target_level"] = 5
            a.profile_snapshot = snap
    seed_answers(store, cid, 6)
    campaign_transition(store, cid, "close")
    r = start_run(store, cid)
    Worker(store).drain()
    with store.session() as s:
        report = metrics(build_snapshot(s, r["id"]))
    assert all(
        x["gap"] is None and x["target_status"] == "not_measured"
        for x in report["rows"]
    )
    assert report["target_met_rate"] is None and report["target_comparison_n"] == 0


def test_committed_grade_recovery_does_not_call_llm_again(store):
    cid = prepared(store)
    seed_answers(store, cid, 1)
    campaign_transition(store, cid, "close")
    start_run(store, cid)
    first = Worker(store)
    job = first.claim()
    first.grade(job)
    with store.session() as s:
        calls = len(list(s.scalars(select(Call))))
        s.execute(update(Job).where(Job.id == job.id).values(lease_until=0))
    second = Worker(store)
    reclaimed = second.claim()
    assert reclaimed.id == job.id and reclaimed.lease_owner != job.lease_owner
    second.grade(reclaimed)
    first.finish(job, "failed")
    with store.session() as s:
        assert len(list(s.scalars(select(Call)))) == calls
        assert s.get(Job, job.id).status == "running"
    second.finish(reclaimed, "done")


def test_generation_recovery_does_not_duplicate_questions(store):
    c = create_campaign(store, "Generation recovery", ["team-data"])
    enqueue_generation(store, c["id"])
    w = Worker(store)
    job = w.claim()
    generate_questions(store, job)
    with store.session() as s:
        before = len(list(s.scalars(select(Question))))
    generate_questions(store, job)
    with store.session() as s:
        assert len(list(s.scalars(select(Question)))) == before == 22

"""Scoped analytics, frozen cohorts and dashboard/Excel parity."""

import copy

import pytest
from openpyxl import load_workbook
from sqlalchemy import select

from app.cli import seed
from app.models import Assignment, Export, Participant, Publication
from app.reporting import metrics
from app.worker import Worker
from test_access import scoped


@pytest.fixture
def snapshot(store):
    seed(store)
    with store.session() as s:
        return copy.deepcopy(s.scalar(select(Publication)).snapshot)


def test_role_filter_keeps_nonrespondents_in_denominator(snapshot):
    report = metrics(snapshot, title="Veri Mühendisi")
    assert report["assigned"] == 10
    assert report["submitted"] == 8
    assert report["completion_rate"] == 80
    assert {row["team_id"] for row in report["rows"]} == {"team-data"}
    assert sum(bucket["count"] for bucket in report["score_distribution"]) == 8
    assert report["team_summary"][0]["not_started"] == 2


def test_skill_filter_keeps_all_eligible_assignees(snapshot):
    skill = next(
        row["skill_id"]
        for row in snapshot["rows"]
        if row["team_id"] == "team-data" and row["section"] == "role"
    )
    report = metrics(snapshot, skill_id=skill)
    assert report["assigned"] == 10 and report["submitted"] == 8
    assert {row["skill_id"] for row in report["rows"]} == {skill}
    assert report["common_n"] == 8
    assert (
        report["common_score"] == metrics(snapshot, team_id="team-data")["common_score"]
    )


def test_section_and_band_filters_do_not_redefine_common_reference(snapshot):
    all_report = metrics(snapshot)
    report = metrics(snapshot, section="role", job_band="L3_L4")
    assert all(row["section"] == "role" for row in report["rows"])
    assert report["common_score"] == all_report["common_score"]
    assert report["common_n"] == 24
    assert report["insights"] == {}
    assert metrics(snapshot, job_band="unknown")["assigned"] == 0


def test_missing_answers_never_turn_into_zero_ability(snapshot):
    report = metrics(snapshot, response_status="not_started")
    assert report["assigned"] == 6 and report["submitted"] == 0
    assert report["rows"] == []
    assert report["common_score"] is None and report["target_met_rate"] is None
    assert report["score_distribution"] == [] and report["levels"] == {}
    assert all(team["common_score"] is None for team in report["team_summary"])


def test_all_aggregate_privacy_thresholds_count_distinct_people(snapshot):
    sample = copy.deepcopy(snapshot)
    ids = {a["id"] for a in sample["assignments"] if a["status"] == "submitted"}
    ids = set(sorted(ids)[:3])
    sample["assignments"] = [a for a in sample["assignments"] if a["id"] in ids]
    sample["rows"] = [r for r in sample["rows"] if r["assignment_id"] in ids]
    assert len(sample["rows"]) == 18
    report = metrics(sample)
    assert report["common_score"] is None
    assert report["levels"] == {} and report["target_met_rate"] is None
    assert report["score_distribution"] == []
    assert all(row["suppressed"] for row in report["aggregates"])


def test_distribution_counts_each_person_once_including_zero_and_hundred(snapshot):
    sample = copy.deepcopy(snapshot)
    pids = sorted({r["participant_id"] for r in sample["rows"]})
    values = [0, 24.999, 25, 49.999, 50, 74.999, 75, 100]
    scores = {pid: values[i % 8] for i, pid in enumerate(pids)}
    for row in sample["rows"]:
        if row["section"] == "common":
            row["written_score"] = scores[row["participant_id"]]
    report = metrics(sample)
    assert report["common_n"] == 24
    assert [bucket["count"] for bucket in report["score_distribution"]] == [6, 6, 6, 6]


def test_different_role_rubrics_are_never_pooled(snapshot):
    sample = copy.deepcopy(snapshot)
    skill = next(
        row["skill_id"]
        for row in sample["rows"]
        if row["team_id"] == "team-data" and row["section"] == "role"
    )
    group = [r for r in sample["rows"] if r["skill_id"] == skill]
    for i, row in enumerate(group):
        row["comparison_group"] = "role-a" if i < 4 else "role-b"
    report = metrics(sample, skill_id=skill)
    assert len(report["aggregates"]) == 2
    assert all(a["n"] == 4 and a["written_score"] is None for a in report["aggregates"])


def test_legacy_publications_enrich_without_changing_frozen_snapshot(
    store, client, snapshot
):
    old = copy.deepcopy(snapshot)
    old["assignments"] = [
        {k: a[k] for k in ("id", "team_id", "status")} for a in old["assignments"]
    ]
    old.pop("common_skill_ids", None)
    with store.session() as s:
        s.get(Publication, old["publication_id"]).snapshot = old
        s.get(Participant, "team-data-person-10").title = "Changed after publication"
    response = client.get(
        f"/api/v1/reports/{old['publication_id']}", params={"title": "Veri Mühendisi"}
    )
    assert response.status_code == 200
    assert response.json()["assigned"] == 10 and response.json()["submitted"] == 8
    assert (
        "Changed after publication" not in response.json()["filter_options"]["titles"]
    )
    with store.session() as s:
        persisted = s.get(Publication, old["publication_id"]).snapshot
        assert persisted == old


def test_filter_options_and_metrics_stay_inside_manager_scope(store, scoped, snapshot):
    _, as_user = scoped
    with as_user("m1") as client:
        response = client.get(f"/api/v1/reports/{snapshot['publication_id']}")
        report = response.json()
        assert response.status_code == 200
        assert report["filter_options"]["titles"] == ["Veri Mühendisi"]
        assert {a["team_id"] for a in report["team_summary"]} == {"team-data"}
        assert report["assigned"] < 10 and report["common_score"] is None
        assert (
            client.get(
                f"/api/v1/reports/{snapshot['publication_id']}",
                params={"team_id": "team-software"},
            ).status_code
            == 404
        )
        assert (
            client.get(
                f"/api/v1/reports/{snapshot['publication_id']}",
                params={"title": "Yazılım Mühendisi"},
            ).json()["assigned"]
            == 0
        )


def test_excel_and_dashboard_share_filters_and_new_aggregates(store, client, snapshot):
    skill = next(
        row["skill_id"]
        for row in snapshot["rows"]
        if row["team_id"] == "team-data" and row["section"] == "role"
    )
    filters = {
        "team_id": "team-data",
        "title": "Veri Mühendisi",
        "section": "role",
        "job_band": "L3_L4",
        "skill_id": skill,
    }
    report = client.get(
        f"/api/v1/reports/{snapshot['publication_id']}", params=filters
    ).json()
    response = client.post(
        "/api/v1/exports",
        json={
            "publication_id": snapshot["publication_id"],
            "filters": filters,
            "detail": True,
        },
    )
    assert response.status_code == 202
    Worker(store).drain()
    with store.session() as s:
        export = s.get(Export, response.json()["id"])
        assert export.filters == filters and export.status == "ready"
        workbook = load_workbook(export.file, data_only=True)
    summary = dict(workbook["Summary"].iter_rows(min_row=2, values_only=True))
    assert summary["assigned"] == report["assigned"]
    assert summary["common_median"] == report["common_median"]
    assert workbook["People_Competency"].max_row - 1 == len(report["rows"])
    assert workbook["Team_Participation"].max_row == 2
    assert (
        sum(
            row[1]
            for row in workbook["Score_Distribution"].iter_rows(min_row=2, values_only=True)
        )
        == report["common_n"]
    )
    assert workbook["Development_Actions"].max_row == 1


@pytest.mark.parametrize(
    "filters",
    [
        {"section": "unsafe"},
        {"response_status": "all"},
        {"title": "x" * 201},
        {"job_band": "x" * 33},
    ],
)
def test_report_filter_validation_is_bounded(client, filters):
    assert client.get("/api/v1/reports/any", params=filters).status_code == 422
    assert (
        client.post(
            "/api/v1/exports", json={"publication_id": "any", "filters": filters}
        ).status_code
        == 422
    )


def test_eligibility_uses_assigned_form_instead_of_unused_role_target(
    store, client, snapshot
):
    old = copy.deepcopy(snapshot)
    old["assignments"] = [
        {k: a[k] for k in ("id", "team_id", "status")} for a in old["assignments"]
    ]
    sid = next(
        r["skill_id"]
        for r in old["rows"]
        if r["team_id"] == "team-software" and r["section"] == "role"
    )
    with store.session() as s:
        s.get(Publication, old["publication_id"]).snapshot = old
        assignment = s.scalar(
            select(Assignment).where(
                Assignment.campaign_id == old["campaign_id"],
                Assignment.participant_id == "team-data-person-10",
            )
        )
        profile = copy.deepcopy(assignment.profile_snapshot)
        profile["role_profile"]["targets"].append(
            {"skill_id": sid, "applicable": True, "target_level": 3, "criticality": 3}
        )
        assignment.profile_snapshot = profile
    report = client.get(
        f"/api/v1/reports/{old['publication_id']}", params={"skill_id": sid}
    ).json()
    assert report["assigned"] == 10 and report["submitted"] == 8
    assert {team["team_id"] for team in report["team_summary"]} == {"team-software"}


def test_target_success_always_exposes_its_measurable_coverage(snapshot):
    report = metrics(snapshot)
    eligible = [
        r
        for r in report["rows"]
        if r["target_level"] is not None and 1 <= r["target_level"] <= 3
    ]
    assert report["target_eligible_n"] == len(eligible)
    assert report["target_coverage_rate"] == round(
        100 * report["target_comparison_n"] / len(eligible), 1
    )
    assert report["target_coverage_rate"] < 100
    sample = copy.deepcopy(snapshot)
    pid = sample["rows"][0]["participant_id"]
    sample["rows"] = [r for r in sample["rows"] if r["participant_id"] == pid]
    sample["assignments"] = [
        a for a in sample["assignments"] if a["participant_id"] == pid
    ]
    small = metrics(sample)
    assert small["target_met_rate"] is None and small["target_coverage_rate"] is None

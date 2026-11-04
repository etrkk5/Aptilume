from collections import defaultdict
from statistics import mean, median
from sqlalchemy import select
from .models import *
from .store import DomainError, get


def build_snapshot(s, run_id):
    run = get(s, Run, run_id)
    campaign = get(s, Campaign, run.campaign_id)
    answers = list(s.scalars(select(Answer).where(Answer.id.in_(run.input_manifest))))
    questions = {
        q.id: q
        for q in s.scalars(select(Question).where(Question.campaign_id == campaign.id))
    }
    ass = {
        a.id: a
        for a in s.scalars(
            select(Assignment).where(Assignment.campaign_id == campaign.id)
        )
    }
    skills = {x.id: x for x in s.scalars(select(Skill))}
    evaluations = {
        (e.answer_id, e.pass_no): e
        for e in s.scalars(select(Evaluation).where(Evaluation.run_id == run_id))
    }
    decisions = {}
    for d in s.scalars(select(ReviewDecision).order_by(ReviewDecision.created_at)):
        decisions[d.evaluation_id] = d
    grouped = defaultdict(list)
    details = []
    rubric_rows = []
    for answer in answers:
        q = questions[answer.question_id]
        a = ass[answer.assignment_id]
        evaluation = evaluations.get((answer.id, 1))
        decision = decisions.get(evaluation.id) if evaluation else None
        score = (
            (
                decision.score
                if decision and decision.score is not None
                else evaluation.score
            )
            if evaluation
            else None
        )
        valid = (
            evaluation
            and (
                evaluation.status == "scored" or decision and decision.score is not None
            )
            and evaluation.review_status != "pending"
        )
        grouped[(a.id, q.skill_id)].append(
            (q, answer, evaluation, score if valid else None, decision)
        )
        details.append(
            {
                "answer_id": answer.id,
                "assignment_id": a.id,
                "participant_id": a.participant_id,
                "team_id": a.profile_snapshot["team"]["id"],
                "skill_id": q.skill_id,
                "question_id": q.id,
                "question_type": q.type,
                "question": q.prompt,
                "text": answer.text,
                "selected": answer.selected,
                "revision": answer.revision,
                "submitted_at": a.submitted_at,
            }
        )
        if evaluation:
            for c in evaluation.criteria:
                rubric_rows.append(
                    {
                        "answer_id": answer.id,
                        "criterion_id": c["criterion_id"],
                        "points": c["points"],
                        "max_points": 4,
                        "quotes": c["evidence_quotes"],
                        "reason": c["reason"],
                        "review_status": evaluation.review_status,
                        "override_score": decision.score if decision else None,
                        "review_reason": decision.reason if decision else None,
                    }
                )
    rows = []
    for (aid, sid), values in grouped.items():
        a = ass[aid]
        team = a.profile_snapshot["team"]
        skill = skills[sid]
        role = a.profile_snapshot.get("role_profile") or team
        targets = {t["skill_id"]: t for t in role["targets"]}
        target = targets.get(sid, {"target_level": None, "criticality": 1})
        written = [v for v in values if v[0].type == "open_text"]
        valid_scores = [v[3] for v in written if v[3] is not None]
        complete = len(written) == 2 and len(valid_scores) == 2
        mcq = [
            int(
                set(v[1].selected)
                == {o["id"] for o in v[0].options if o.get("correct")}
            )
            for v in values
            if v[0].type in ["single_choice", "multi_choice"]
        ]
        self_value = next(
            (
                v[1].selected[0]
                for v in values
                if v[0].type == "self_assessment" and v[1].selected
            ),
            None,
        )
        level = None
        if complete and not any(v[4] and v[4].score is not None for v in written):
            for k in range(1, 4):
                supporting = set()
                covered = set()
                for q, ans, e, score, decision in written:
                    rubric = {r["id"]: r for r in q.rubric}
                    for criterion in e.criteria:
                        r = rubric[criterion["criterion_id"]]
                        if r["level"] <= k and criterion["points"] >= 3:
                            covered.add(r["level"])
                            supporting.add(q.id)
                if covered == set(range(1, k + 1)) and len(supporting) >= 2:
                    level = k
        self_level = int(self_value) if self_value and self_value.isdigit() else None
        comparison_group = (
            "common-v1"
            if sid in campaign.config["common_skills"]
            else f"{role['id']}-v{role['version']}"
        )
        rows.append(
            {
                "assignment_id": aid,
                "participant_id": a.participant_id,
                "name": a.profile_snapshot["name"],
                "title": a.profile_snapshot["title"],
                "job_band": a.profile_snapshot["job_band"],
                "team_id": team["id"],
                "team_name": team["name"],
                "skill_id": sid,
                "skill_name": skill.name,
                "section": (
                    "common" if sid in campaign.config["common_skills"] else "role"
                ),
                "comparison_group": comparison_group,
                "target_level": target["target_level"],
                "criticality": target["criticality"],
                "written_score": round(mean(valid_scores), 4) if complete else None,
                "mcq_score": 100 * mean(mcq) if mcq else None,
                "self_level": self_level,
                "self_category": self_value,
                "suggested_level": level,
                "validated_level": None,
                "gap": (
                    max(target["target_level"] - level, 0)
                    if level and target["target_level"] and target["target_level"] <= 3
                    else None
                ),
                "target_status": (
                    "not_measured"
                    if target["target_level"] and target["target_level"] > 3
                    else "measured"
                ),
                "self_gap": (
                    self_level - level
                    if self_level and self_level <= 3 and level
                    else None
                ),
                "coverage": len(valid_scores) / 2,
                "status": "complete" if complete else "incomplete",
                "levels_not_measured": [4, 5],
            }
        )
    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "run_id": run.id,
        "input_hash": run.input_hash,
        "created_at": now(),
        "scoring_version": "rubric-v1",
        "level_rule": "indicator-v1",
        "profile_version": run.profile_version,
        "mock": run.profile_version
        and any(e.usage.get("simulated") for e in evaluations.values()),
        "assignments": [
            {
                "id": a.id,
                "team_id": a.profile_snapshot["team"]["id"],
                "status": a.status,
            }
            for a in ass.values()
        ],
        "rows": rows,
        "answers": details,
        "rubric_scores": rubric_rows,
        "insights": run.insights,
    }


def metrics(snapshot, team_id=None, skill_id=None):
    rows = [
        r
        for r in snapshot["rows"]
        if (not team_id or r["team_id"] == team_id)
        and (not skill_id or r["skill_id"] == skill_id)
    ]
    assignments = [
        a for a in snapshot["assignments"] if not team_id or a["team_id"] == team_id
    ]
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["team_id"], r["skill_id"], r["comparison_group"])].append(r)
    aggregates = []
    for (tid, sid, cg), items in grouped.items():
        valid = [r for r in items if r["written_score"] is not None]
        levels = [r for r in items if r["suggested_level"] is not None]
        gaps = [r["gap"] for r in items if r["gap"] is not None]
        suppressed = len(valid) < 5
        aggregates.append(
            {
                "team_id": tid,
                "team_name": items[0]["team_name"],
                "skill_id": sid,
                "skill_name": items[0]["skill_name"],
                "section": items[0]["section"],
                "comparison_group": cg,
                "n": len(valid),
                "missing": len(items) - len(valid),
                "suppressed": suppressed,
                "written_score": (
                    round(mean(r["written_score"] for r in valid), 1)
                    if valid and not suppressed
                    else None
                ),
                "target_level": items[0]["target_level"],
                "level_coverage": len(levels),
                "mean_gap": (round(mean(gaps), 2) if gaps and not suppressed else None),
            }
        )
    common = [
        r for r in rows if r["section"] == "common" and r["written_score"] is not None
    ]
    people = defaultdict(list)
    for r in common:
        people[r["participant_id"]].append(r["written_score"])
    person_scores = [mean(v) for v in people.values() if len(v) == 3]
    valid_levels = [r for r in rows if r["suggested_level"] is not None]
    comparable_targets = [r for r in valid_levels if r["gap"] is not None]
    levels = {
        str(i): sum(r["suggested_level"] == i for r in valid_levels)
        for i in range(1, 6)
    }
    submitted = sum(a["status"] == "submitted" for a in assignments)
    suppress_overall = len(person_scores) < 5
    return {
        "publication_id": snapshot.get("publication_id"),
        "campaign_name": snapshot["campaign_name"],
        "run_id": snapshot["run_id"],
        "mock": bool(snapshot["mock"]),
        "assigned": len(assignments),
        "submitted": submitted,
        "completion_rate": (
            round(100 * submitted / len(assignments), 1) if assignments else 0
        ),
        "common_score": (
            round(mean(person_scores), 1)
            if person_scores and not suppress_overall
            else None
        ),
        "common_median": (
            round(median(person_scores), 1)
            if person_scores and not suppress_overall
            else None
        ),
        "common_n": len(person_scores),
        "complete_people": len(
            {r["participant_id"] for r in rows if r["status"] == "complete"}
        ),
        "level_coverage": len(valid_levels),
        "target_met_rate": (
            round(
                100
                * sum(r["gap"] == 0 for r in comparable_targets)
                / len(comparable_targets),
                1,
            )
            if len(comparable_targets) >= 5
            else None
        ),
        "target_comparison_n": len(comparable_targets),
        "levels": levels if len(valid_levels) >= 5 else {},
        "aggregates": aggregates,
        "rows": rows,
        "insights": snapshot.get("insights", {}),
        "filters": {"team_id": team_id, "skill_id": skill_id},
    }


def publish(store, rid):
    with store.session() as s:
        r = get(s, Run, rid)
        existing = s.scalar(select(Publication).where(Publication.run_id == rid))
        if existing:
            return existing.id
        if r.status != "ready_to_publish":
            raise DomainError(
                "not_ready", "İşler ve gerekli incelemeler tamamlanmalı.", 409
            )
        snap = build_snapshot(s, rid)
        if any(row["status"] != "complete" for row in snap["rows"]):
            raise DomainError(
                "incomplete_results",
                "Eksik puanlar tamamlanmadan sonuç yayımlanamaz.",
                409,
            )
        version = (
            len(
                list(
                    s.scalars(
                        select(Publication).where(
                            Publication.campaign_id == r.campaign_id
                        )
                    )
                )
            )
            + 1
        )
        pid = uid()
        snap["publication_id"] = pid
        p = Publication(
            id=pid,
            run_id=rid,
            campaign_id=r.campaign_id,
            version=version,
            snapshot=snap,
        )
        s.add(p)
        get(s, Campaign, r.campaign_id).publication_id = pid
        r.status = "published"
        s.add(
            Audit(
                action="results_published",
                entity_id=pid,
                detail={"run_id": rid, "version": version},
            )
        )
        return pid

from collections import defaultdict, Counter
from statistics import mean, median
from sqlalchemy import select, func
from .models import *
from .store import DomainError, get


def build_snapshot(s, run_id):
    run = get(s, Run, run_id)
    campaign = get(s, Campaign, run.campaign_id)
    instruction_policy = s.get(RunPolicy, run_id)
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
    assigned_skills = assignment_skills(s, ass)
    expected_written = {
        (aid, sid): count
        for aid, sid, count in s.execute(
            select(AssignedQuestion.assignment_id, Question.skill_id, func.count())
            .join(Question, Question.id == AssignedQuestion.question_id)
            .where(
                AssignedQuestion.assignment_id.in_(list(ass)),
                Question.type == "open_text",
            )
            .group_by(AssignedQuestion.assignment_id, Question.skill_id)
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
        expected = expected_written.get((aid, sid), 0)
        complete = (
            expected > 0 and len(written) == expected and len(valid_scores) == expected
        )
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
        group_key = "common" if sid in campaign.config["common_skills"] else role["id"]
        if campaign.config.get("question_form_hashes", {}).get(group_key):
            comparison_group += (
                "-q" + campaign.config["question_form_hashes"][group_key]
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
                "skill_name": campaign.config.get("skill_snapshots", {})
                .get(sid, {})
                .get("name", skill.name),
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
                "coverage": len(valid_scores) / expected if expected else 0,
                "expected_written_questions": expected,
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
        "common_skill_ids": campaign.config["common_skills"],
        "question_set_revision": campaign.config.get("question_set_revision", 1),
        "question_approval": campaign.config.get("question_approval"),
        "prompt_policy": {
            "generation_id": campaign.config.get("generation_policy_id"),
            "generation_version": campaign.config.get("generation_policy_version"),
            "evaluation_id": (
                instruction_policy.policy_id if instruction_policy else None
            ),
            "evaluation_version": (
                instruction_policy.version if instruction_policy else None
            ),
        },
        "scoring_version": "rubric-v1",
        "level_rule": "indicator-v1",
        "profile_version": run.profile_version,
        "mock": run.profile_version
        and any(e.usage.get("simulated") for e in evaluations.values()),
        "assignments": [
            assignment_metadata(a, assigned_skills.get(a.id, [])) for a in ass.values()
        ],
        "rows": rows,
        "answers": details,
        "rubric_scores": rubric_rows,
        "insights": run.insights,
    }


def assignment_skills(s, ids):
    result = defaultdict(set)
    for aid, sid in s.execute(
        select(AssignedQuestion.assignment_id, Question.skill_id)
        .join(Question, AssignedQuestion.question_id == Question.id)
        .where(AssignedQuestion.assignment_id.in_(list(ids)))
        .distinct()
    ):
        result[aid].add(sid)
    return result


def assignment_metadata(assignment, skill_ids):
    profile = assignment.profile_snapshot
    team = profile["team"]
    role = profile.get("role_profile") or team
    return {
        "id": assignment.id,
        "participant_id": assignment.participant_id,
        "team_id": team["id"],
        "team_name": team["name"],
        "title": profile.get("title", ""),
        "job_band": profile.get("job_band", ""),
        "role_title": role.get("title", profile.get("title", "")),
        "skill_ids": sorted(skill_ids),
        "status": assignment.status,
    }


def enrich_snapshot(s, snapshot):
    """Read frozen assignment context for older publications without mutating them."""
    missing = [a["id"] for a in snapshot["assignments"] if "participant_id" not in a]
    skills = assignment_skills(s, missing) if missing else {}
    metadata = (
        {
            a.id: assignment_metadata(a, skills.get(a.id, []))
            for a in s.scalars(select(Assignment).where(Assignment.id.in_(missing)))
        }
        if missing
        else {}
    )
    return {
        **snapshot,
        "assignments": [
            {**metadata.get(a["id"], {}), **a} for a in snapshot["assignments"]
        ],
    }


def metrics(
    snapshot,
    team_id=None,
    skill_id=None,
    title=None,
    job_band=None,
    section=None,
    response_status=None,
):
    filters = {
        k: v
        for k, v in {
            "team_id": team_id,
            "skill_id": skill_id,
            "title": title,
            "job_band": job_band,
            "section": section,
            "response_status": response_status,
        }.items()
        if v
    }
    all_rows = snapshot["rows"]
    row_people = {r["assignment_id"]: r for r in all_rows}
    # Older in-memory snapshots can still be measured; API/export enrich historical
    # assignments first, so nonrespondents retain their role and eligibility too.
    all_assignments = [
        {**row_people.get(a["id"], {}), **a} for a in snapshot["assignments"]
    ]
    skill_assignments = {
        r["assignment_id"] for r in all_rows if r["skill_id"] == skill_id
    }
    assignments = [
        a
        for a in all_assignments
        if (not team_id or a["team_id"] == team_id)
        and (not title or a.get("title") == title)
        and (not job_band or a.get("job_band") == job_band)
        and (not response_status or a["status"] == response_status)
        and (
            not skill_id
            or skill_id in a.get("skill_ids", [])
            or a["id"] in skill_assignments
        )
    ]
    allowed = {a["id"] for a in assignments}
    cohort_rows = [r for r in all_rows if r["assignment_id"] in allowed]
    rows = [
        r
        for r in cohort_rows
        if (not skill_id or r["skill_id"] == skill_id)
        and (not section or r["section"] == section)
    ]
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["team_id"], r["skill_id"], r["comparison_group"])].append(r)
    aggregates = []
    for (tid, sid, cg), items in grouped.items():
        valid = [r for r in items if r["written_score"] is not None]
        n = len({r["participant_id"] for r in valid})
        levels = [r for r in items if r["suggested_level"] is not None]
        gaps = [r["gap"] for r in items if r["gap"] is not None]
        suppressed = n < 5
        aggregates.append(
            {
                "team_id": tid,
                "team_name": items[0]["team_name"],
                "skill_id": sid,
                "skill_name": items[0]["skill_name"],
                "section": items[0]["section"],
                "comparison_group": cg,
                "role_title": " / ".join(sorted({r["title"] for r in items})),
                "n": n,
                "missing": len(items) - len(valid),
                "suppressed": suppressed,
                "written_score": (
                    round(mean(r["written_score"] for r in valid), 1)
                    if valid and not suppressed
                    else None
                ),
                "target_level": items[0]["target_level"],
                "level_coverage": len(levels),
                "mean_gap": round(mean(gaps), 2) if gaps and not suppressed else None,
            }
        )
    expected = set(
        snapshot.get("common_skill_ids")
        or [r["skill_id"] for r in all_rows if r["section"] == "common"]
    )
    people = defaultdict(dict)
    for r in cohort_rows:
        if r["section"] == "common" and r["written_score"] is not None:
            people[r["participant_id"]][r["skill_id"]] = r["written_score"]
    person_scores = {
        pid: mean(values.values())
        for pid, values in people.items()
        if len(expected) == 3 and set(values) == expected
    }
    common_values = list(person_scores.values())
    valid_levels = [r for r in rows if r["suggested_level"] is not None]
    comparable = [r for r in valid_levels if r["gap"] is not None]
    eligible_targets = [
        r for r in rows if r["target_level"] is not None and 1 <= r["target_level"] <= 3
    ]
    enough_target_scope = len({r["participant_id"] for r in eligible_targets}) >= 5
    enough_levels = len({r["participant_id"] for r in valid_levels}) >= 5
    enough_targets = len({r["participant_id"] for r in comparable}) >= 5
    suppressed = len(common_values) < 5
    submitted = sum(a["status"] == "submitted" for a in assignments)
    team_summary = []
    for tid in sorted({a["team_id"] for a in assignments}):
        members = [a for a in assignments if a["team_id"] == tid]
        scores = [
            person_scores[a["participant_id"]]
            for a in members
            if a.get("participant_id") in person_scores
        ]
        states = Counter(a["status"] for a in members)
        team_summary.append(
            {
                "team_id": tid,
                "team_name": members[0].get("team_name", tid),
                "assigned": len(members),
                "submitted": states["submitted"],
                "draft": states["draft"],
                "not_started": len(members) - states["submitted"] - states["draft"],
                "completion_rate": round(100 * states["submitted"] / len(members), 1),
                "common_n": len(scores),
                "suppressed": len(scores) < 5,
                "common_score": round(mean(scores), 1) if len(scores) >= 5 else None,
            }
        )
    bins = [
        ("0–<25", 0, 25),
        ("25–<50", 25, 50),
        ("50–<75", 50, 75),
        ("75–100", 75, 101),
    ]
    options = {
        "titles": sorted({a.get("title") for a in all_assignments if a.get("title")}),
        "job_bands": sorted(
            {a.get("job_band") for a in all_assignments if a.get("job_band")}
        ),
        "skills": [
            {"id": sid, "name": name, "section": sec}
            for sid, name, sec in sorted(
                {(r["skill_id"], r["skill_name"], r["section"]) for r in all_rows},
                key=lambda x: x[1],
            )
        ],
    }
    return {
        "prompt_policy": snapshot.get(
            "prompt_policy", {"generation_version": None, "evaluation_version": None}
        ),
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
            round(mean(common_values), 1) if common_values and not suppressed else None
        ),
        "common_median": (
            round(median(common_values), 1)
            if common_values and not suppressed
            else None
        ),
        "common_n": len(common_values),
        "complete_people": len(
            {r["participant_id"] for r in rows if r["status"] == "complete"}
        ),
        "level_coverage": len(valid_levels),
        "target_met_rate": (
            round(100 * sum(r["gap"] == 0 for r in comparable) / len(comparable), 1)
            if enough_targets
            else None
        ),
        "target_comparison_n": len(comparable),
        "target_eligible_n": len(eligible_targets),
        "target_coverage_rate": (
            round(100 * len(comparable) / len(eligible_targets), 1)
            if eligible_targets and enough_target_scope
            else None
        ),
        "target_comparison_people": len({r["participant_id"] for r in comparable}),
        "levels": (
            {
                str(i): sum(r["suggested_level"] == i for r in valid_levels)
                for i in range(1, 6)
            }
            if enough_levels
            else {}
        ),
        "unmeasured_level_count": len(rows) - len(valid_levels),
        "score_distribution": (
            [
                {"label": label, "count": sum(lo <= v < hi for v in common_values)}
                for label, lo, hi in bins
            ]
            if not suppressed
            else []
        ),
        "distribution_suppressed": suppressed,
        "team_summary": team_summary,
        "aggregates": sorted(
            aggregates,
            key=lambda x: (x["team_name"], x["comparison_group"], x["skill_name"]),
        ),
        "rows": rows,
        "insights": snapshot.get("insights", {}) if not filters else {},
        "filters": filters,
        "filter_options": options,
        "methodology": {
            "minimum_people": 5,
            "common_score_scope": "Seçili çalışan kapsamındaki üç ortak yetkinliğin kişi bazlı ortalaması. Yetkinlik/bölüm seçimi bu referans ölçütünü değiştirmez; yetkinlik seçimi uygulanabilir çalışan kapsamını daraltır.",
            "level_unit": "kişi-yetkinlik gözlemi",
            "role_comparison": "Role özel puanlar yalnız aynı karşılaştırma grubunda yorumlanır.",
        },
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

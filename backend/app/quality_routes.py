"""HR-only inbox, derived from durable post-campaign worker evaluations."""

from typing import Literal
from fastapi import Query
from sqlalchemy import select, func
from .models import (
    QualityIssue,
    Evaluation,
    Answer,
    Question,
    Assignment,
    Campaign,
    ReviewDecision,
)
from .access import require_hr
from .store import DomainError


def install_quality_routes(app, store):
    def query():
        return (
            select(QualityIssue, Evaluation, Answer, Question, Assignment, Campaign)
            .join(Evaluation, QualityIssue.evaluation_id == Evaluation.id)
            .join(Answer, QualityIssue.answer_id == Answer.id)
            .join(Question, Answer.question_id == Question.id)
            .join(Assignment, Answer.assignment_id == Assignment.id)
            .join(Campaign, Assignment.campaign_id == Campaign.id)
        )

    def serialize(row, detail=False, session=None):
        issue, evaluation, answer, question, assignment, campaign = row
        profile = assignment.profile_snapshot
        value = {
            "id": issue.id,
            "evaluation_id": evaluation.id,
            "run_id": issue.run_id,
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "participant_id": assignment.participant_id,
            "name": profile["name"],
            "team_id": profile["team"]["id"],
            "team_name": profile["team"]["name"],
            "category": issue.category,
            "reason": issue.reason,
            "source": issue.source,
            "created_at": issue.created_at,
            "review_status": evaluation.review_status,
            "pass_no": evaluation.pass_no,
            "question": question.prompt if detail else question.prompt[:300],
            "answer": answer.text if detail else answer.text[:240],
        }
        if detail:
            actor = require_hr()
            decision = session.scalar(
                select(ReviewDecision)
                .where(ReviewDecision.evaluation_id == evaluation.id)
                .order_by(ReviewDecision.created_at.desc())
                .limit(1)
            )
            value.update(
                {
                    "evidence_quotes": issue.evidence_quotes,
                    "criteria": evaluation.criteria,
                    "can_review": evaluation.review_status == "pending"
                    and assignment.participant_id != actor.participant_id,
                    "self_review": assignment.participant_id == actor.participant_id,
                    "decision": (
                        {
                            "score": decision.score,
                            "reason": decision.reason,
                            "reviewer": decision.reviewer,
                            "created_at": decision.created_at,
                        }
                        if decision
                        else None
                    ),
                }
            )
        return value

    @app.get("/api/v1/quality-cases")
    def cases(
        status: Literal["pending", "resolved", "all"] = "pending",
        team_id: str | None = Query(default=None, max_length=64),
        campaign_id: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=25, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=100000),
    ):
        require_hr()
        with store.session() as s:
            base = query()
            if team_id:
                base = base.where(
                    Assignment.profile_snapshot["team"]["id"].as_string() == team_id
                )
            if campaign_id:
                base = base.where(Campaign.id == campaign_id)
            cohort = base.with_only_columns(
                QualityIssue.id, Evaluation.review_status, Assignment.participant_id
            ).subquery()
            counts = dict(
                s.execute(
                    select(cohort.c.review_status, func.count()).group_by(
                        cohort.c.review_status
                    )
                ).all()
            )
            people = s.scalar(
                select(func.count(func.distinct(cohort.c.participant_id)))
            )
            selected = (
                base
                if status == "all"
                else base.where(Evaluation.review_status == status)
            )
            total = s.scalar(select(func.count()).select_from(selected.subquery()))
            rows = s.execute(
                selected.order_by(QualityIssue.created_at.desc(), QualityIssue.id)
                .offset(offset)
                .limit(limit)
            ).all()
            return {
                "items": [serialize(row) for row in rows],
                "total": total,
                "offset": offset,
                "limit": limit,
                "summary": {
                    "pending": counts.get("pending", 0),
                    "resolved": counts.get("resolved", 0),
                    "people": people,
                },
            }

    @app.get("/api/v1/quality-cases/{case_id}")
    def case(case_id: str):
        require_hr()
        with store.session() as s:
            row = s.execute(query().where(QualityIssue.id == case_id)).first()
            if not row:
                raise DomainError("not_found", "İnceleme kaydı bulunamadı.", 404)
            return serialize(row, detail=True, session=s)

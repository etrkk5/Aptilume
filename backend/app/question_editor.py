"""HR-owned draft questions, optimistic locks and explicit publication validation."""

from collections import Counter
import hashlib
import json
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from .access import require_hr, check_campaign
from .models import Campaign, Question, Assignment, Audit, now
from .store import DomainError, get
from .validation import GeneratedQuestion


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)


class DraftQuestion(GeneratedQuestion):
    model_config = ConfigDict(extra="forbid", strict=True)
    form_key: str = Field(min_length=1, max_length=64)
    expected_version: int = Field(ge=1)


def groups(config):
    from .services import COMMON

    common = config.get("common_skills", COMMON)
    result = [{"id": "common", "name": "Ortak soru seti", "skill_ids": common}]
    profiles = config.get("role_snapshots") or config.get("team_snapshots", {})
    for pid, profile in profiles.items():
        team = config["team_snapshots"].get(profile.get("team_id", pid), {})
        result.append(
            {
                "id": pid,
                "name": f"{team.get('name', profile.get('name', 'Ekip'))} · {profile.get('title', profile.get('role', 'Rol'))}",
                "skill_ids": [
                    t["skill_id"]
                    for t in profile.get("targets", [])
                    if t.get("applicable", True) and t["skill_id"] not in common
                ][:3],
            }
        )
    return result


def question_data(q):
    return {
        "id": q.id,
        "form_key": q.form_key,
        "skill_id": q.skill_id,
        "type": q.type,
        "prompt": q.prompt,
        "section": q.section,
        "position": q.position,
        "version": q.version,
        "rubric": q.rubric,
        "options": q.options,
        "reference": q.reference.removesuffix("\nEXPERIENCE"),
        "evidence_type": (
            "self_reported_experience"
            if q.reference.endswith("\nEXPERIENCE")
            else "scenario_reasoning"
        ),
    }


def lock_campaign(s, cid, version=None, statuses=("content_review", "ready")):
    c = get(s, Campaign, cid)
    conditions = [Campaign.id == cid, Campaign.status.in_(statuses)]
    if version is not None:
        conditions.append(Campaign.row_version == version)
    changed = s.execute(
        update(Campaign).where(*conditions).values(row_version=Campaign.row_version)
    )
    if changed.rowcount != 1:
        raise DomainError(
            "question_set_conflict",
            "Soru seti değişmiş veya bu durumda düzenlemeye kapalı. Güncel seti yükleyin.",
            409,
        )
    s.refresh(c)
    return c


def validate_question(q, config):
    allowed = {g["id"]: g["skill_ids"] for g in groups(config)}
    if q.form_key not in allowed or q.skill_id not in allowed[q.form_key]:
        raise DomainError(
            "invalid_question_scope",
            "Sorunun yetkinliği seçilen ortak/rol setine ait olmalı.",
        )
    if not q.prompt.strip():
        raise DomainError("invalid_question", "Soru metni boş olamaz.")
    options = q.options
    if (
        any(not o.text.strip() for o in options)
        or len({o.id for o in options}) != len(options)
        or len({o.text.strip().casefold() for o in options}) != len(options)
    ):
        raise DomainError(
            "invalid_options",
            "Seçenekler boş olamaz; kimlik ve metinleri benzersiz olmalı.",
        )
    if q.type == "open_text":
        if (
            options
            or len(q.rubric) < 3
            or {r.level for r in q.rubric} != {1, 2, 3}
            or len({r.id for r in q.rubric}) != len(q.rubric)
        ):
            raise DomainError(
                "invalid_rubric",
                "Açık uçlu soruda seçenek bulunamaz; L1–L3 ölçütleri ve benzersiz kriterler gerekli.",
            )
        if any(
            not r.id.strip()
            or not r.label.strip()
            or not r.descriptor.strip()
            or set(r.anchors) != {"0", "1", "2", "3", "4"}
            or any(not v.strip() or len(v) > 1000 for v in r.anchors.values())
            for r in q.rubric
        ):
            raise DomainError(
                "invalid_rubric",
                "Ölçüt adı, davranış tanımı ve 0–4 puan açıklamalarının tamamını girin.",
            )
    elif q.rubric:
        raise DomainError(
            "invalid_rubric",
            "Puanlama ölçütleri yalnız açık uçlu sorularda kullanılır.",
        )
    if q.type == "single_choice":
        if (
            not 2 <= len(options) <= 6
            or sum(o.correct for o in options) != 1
            or any(o.level is not None for o in options)
        ):
            raise DomainError(
                "invalid_answer_key",
                "Tek seçim sorusunda 2–6 seçenek ve tam bir doğru cevap gerekli.",
            )
    if q.type == "self_assessment":
        if {o.id for o in options} != {"1", "2", "3", "4", "5", "none"} or any(
            o.correct or o.level != (None if o.id == "none" else int(o.id))
            for o in options
        ):
            raise DomainError(
                "invalid_self_options",
                "Öz beyan L1–L5 ve deneyimim yok seçeneklerini korumalı; doğru cevap içermez.",
            )
    return q


def publication_issues(config, questions):
    issues = []
    by_form = {g["id"]: [] for g in groups(config)}
    for q in questions:
        if q.form_key not in by_form:
            issues.append("Tanımsız rol grubuna ait soru var.")
            continue
        by_form[q.form_key].append(q)
        try:
            validate_question(
                DraftQuestion(
                    **{
                        k: v
                        for k, v in question_data(q).items()
                        if k not in {"id", "position", "version"}
                    },
                    expected_version=1,
                ),
                config,
            )
        except (DomainError, ValueError):
            issues.append(f"Geçersiz soru veya puanlama ölçütü: {q.prompt[:70]}")
    for group in groups(config):
        rows = by_form[group["id"]]
        for sid in group["skill_ids"]:
            counts = Counter(q.type for q in rows if q.skill_id == sid)
            if counts["open_text"] < 1 or counts["self_assessment"] != 1:
                name = config.get("skill_snapshots", {}).get(sid, {}).get("name", sid)
                issues.append(
                    f"{group['name']} / {name}: en az bir açık uçlu ve tam bir öz beyan sorusu gerekli."
                )
        if not group["skill_ids"]:
            issues.append(f"{group['name']}: ölçülecek yetkinlik yok.")
    common = len(by_form["common"])
    for group in groups(config)[1:]:
        if not 1 <= common + len(by_form[group["id"]]) <= 60:
            issues.append(
                f"{group['name']}: katılımcı başına soru sayısı 1–60 aralığında olmalı."
            )
    return list(dict.fromkeys(issues))


def validate_publication(s, c):
    rows = list(s.scalars(select(Question).where(Question.campaign_id == c.id)))
    errors = publication_issues(c.config, rows)
    if not rows or errors:
        raise DomainError(
            "invalid_question_set",
            "Yayın öncesi soru setini tamamlayın. " + " ".join(errors[:8]),
            409,
        )
    return rows


def set_counts(config, questions):
    return {
        g["id"]: sum(q.form_key in {"common", g["id"]} for q in questions)
        for g in groups(config)[1:]
    }


def form_hashes(config, questions):
    return {
        g["id"]: hashlib.sha256(
            json.dumps(
                [
                    {
                        k: v
                        for k, v in question_data(q).items()
                        if k not in {"id", "position", "version"}
                    }
                    for q in sorted(questions, key=lambda q: (q.position, q.id))
                    if q.form_key in {"common", g["id"]}
                ],
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()[:16]
        for g in groups(config)
    }


def editor_view(s, c, actor):
    from .catalog import freeze_skills

    questions = list(
        s.scalars(
            select(Question)
            .where(Question.campaign_id == c.id)
            .order_by(Question.position, Question.id)
        )
    )
    form_groups = groups(c.config)
    for group in form_groups:
        group["count"] = sum(q.form_key == group["id"] for q in questions)
        group["participant_question_count"] = group["count"] + (
            sum(q.form_key == "common" for q in questions)
            if group["id"] != "common"
            else 0
        )
    return {
        "id": c.id,
        "name": c.name,
        "status": c.status,
        "version": c.row_version,
        "revision": c.config.get("question_set_revision", 1),
        "approval": c.config.get("question_approval"),
        "can_edit": actor.hr and c.status in {"content_review", "ready"},
        "groups": form_groups,
        "skills": c.config.get("skill_snapshots")
        or freeze_skills(s, c.config, allow_archived=True),
        "questions": [question_data(q) for q in questions],
        "issues": publication_issues(c.config, questions),
    }


def changed(c, actor):
    c.row_version += 1
    c.config = {
        **c.config,
        "question_set_revision": c.config.get("question_set_revision", 1) + 1,
        "question_approval": None,
    }
    c.status = "content_review"


def install_question_editor(app, store):
    @app.get("/api/v1/campaigns/{cid}/question-set")
    def view(cid: str):
        from .security import current_actor

        with store.session() as s:
            c = check_campaign(s, cid, write=True)
            return editor_view(s, c, current_actor())

    def mutation(cid, version, value=None, qid=None, remove=False):
        actor = require_hr()
        from .throttle import reserve

        reserve(store, "question-write", actor.id, 120, 60)
        with store.session() as s:
            c = lock_campaign(s, cid, version)
            if s.scalar(
                select(Assignment.id).where(Assignment.campaign_id == cid).limit(1)
            ):
                raise DomainError(
                    "question_set_frozen",
                    "Atanmış anketin soru seti değiştirilemez.",
                    409,
                )
            q = get(s, Question, qid) if qid else Question(campaign_id=cid)
            if q.campaign_id != cid:
                raise DomainError("not_found", "Soru bulunamadı.", 404)
            before = question_data(q) if qid else None
            if remove:
                s.delete(q)
            else:
                validate_question(value, c.config)
                if not qid:
                    total = len(
                        list(
                            s.scalars(
                                select(Question.id).where(
                                    Question.campaign_id == cid,
                                    Question.form_key.in_(["common", value.form_key]),
                                )
                            )
                        )
                    )
                    if total >= 60:
                        raise DomainError(
                            "question_limit", "Bu set için soru sınırına ulaşıldı.", 409
                        )
                    q.position = (
                        max(
                            (
                                n
                                for n in s.scalars(
                                    select(Question.position).where(
                                        Question.campaign_id == cid
                                    )
                                )
                            ),
                            default=-1,
                        )
                        + 1
                    )
                    s.add(q)
                q.form_key, q.skill_id, q.type = (
                    value.form_key,
                    value.skill_id,
                    value.type,
                )
                q.prompt = value.prompt.strip()
                q.section = "common" if value.form_key == "common" else "role"
                q.rubric = [
                    {**r.model_dump(), "indicator_id": f"{value.skill_id}:L{r.level}"}
                    for r in value.rubric
                ]
                q.options = [o.model_dump() for o in value.options]
                q.reference = value.reference.removesuffix("\nEXPERIENCE").strip() + (
                    "\nEXPERIENCE"
                    if value.evidence_type == "self_reported_experience"
                    else ""
                )
                q.version = (q.version or 0) + 1
                s.flush()
            changed(c, actor)
            s.flush()
            c.config = {
                **c.config,
                "question_counts": set_counts(
                    c.config,
                    list(
                        s.scalars(select(Question).where(Question.campaign_id == cid))
                    ),
                ),
            }
            s.add(
                Audit(
                    action=(
                        "question_deleted"
                        if remove
                        else "question_updated" if qid else "question_created"
                    ),
                    entity_id=cid,
                    detail={
                        "actor_id": actor.id,
                        "question_id": qid or q.id,
                        "before": before,
                        "after": None if remove else question_data(q),
                        "set_revision": c.config["question_set_revision"],
                    },
                )
            )
            return editor_view(s, c, actor)

    @app.post("/api/v1/campaigns/{cid}/questions", status_code=201)
    def add(cid: str, value: DraftQuestion):
        return mutation(cid, value.expected_version, value=value)

    @app.patch("/api/v1/campaigns/{cid}/questions/{qid}")
    def edit(cid: str, qid: str, value: DraftQuestion):
        return mutation(cid, value.expected_version, value=value, qid=qid)

    @app.delete("/api/v1/campaigns/{cid}/questions/{qid}")
    def delete(cid: str, qid: str, expected_version: int = Query(ge=1)):
        return mutation(cid, expected_version, qid=qid, remove=True)

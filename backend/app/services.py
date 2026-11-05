import hashlib
import json
from collections import defaultdict
from pathlib import Path
from sqlalchemy import select, update
from .config import ROOT, REFERENCE_DIR
from .models import *
from .store import DomainError, get
from .providers import Provider

COMMON = ["SKILL-001", "SKILL-002", "SKILL-004"]


def asdict(obj, exclude=()):
    return {
        c.name: getattr(obj, c.key)
        for c in obj.__mapper__.columns
        if c.name not in exclude
    }


def load_catalog(store):
    data = json.loads((REFERENCE_DIR / "catalog.json").read_text())
    with store.session() as s:
        for item in data["skills"]:
            if not s.get(Skill, item["id"]):
                s.add(
                    Skill(
                        id=item["id"],
                        code=item["code"],
                        name=item["name"],
                        definition=item["definition"],
                        levels=item["levels"],
                        metadata_={
                            k: v
                            for k, v in item.items()
                            if k not in ["id", "code", "name", "definition", "levels"]
                        },
                    )
                )
    return {
        "skills": len(data["skills"]),
        "levels": sum(len(x["levels"]) for x in data["skills"]),
        "issues": data["import_issues"],
        "source": data["source"],
    }


def seed_people(store):
    with store.session() as s:
        if s.scalar(select(Team.id)):
            return
        definitions = [
            (
                "team-data",
                "Data & Analytics",
                "Veri Mühendisi",
                [5, 22, 34],
                "Analitik ve RAG veri akışları; tazelik, lineage ve veri doğrulama.",
            ),
            (
                "team-software",
                "Software Engineering",
                "Yazılım Mühendisi",
                [12, 13, 15],
                "Güvenilir yazılım geliştirme; kod inceleme, test ve hata çözümü.",
            ),
            (
                "team-platform",
                "Platform & Operations",
                "Platform Mühendisi",
                [26, 28, 32],
                "AI iş yükleri, kapasite planlama, gözlemlenebilirlik ve olay yönetimi.",
            ),
        ]
        for tid, name, role, codes, context in definitions:
            targets = [
                {
                    "skill_id": sid,
                    "target_level": 3,
                    "criticality": 4,
                    "applicable": True,
                }
                for sid in COMMON + [f"SKILL-{n:03}" for n in codes]
            ]
            s.add(
                Team(
                    id=tid,
                    name=name,
                    role=role,
                    context={
                        "purpose": context,
                        "tasks": [
                            "İş çıktısını doğrulama",
                            "Tekrarlanabilir süreç tasarlama",
                        ],
                        "tools": ["Kurum onaylı AI araçları"],
                        "constraints": "Gerçek müşteri verisi kullanmayın.",
                        "synthetic": True,
                    },
                    targets=targets,
                )
            )
            s.flush()
            names = [
                "Deniz",
                "Ekin",
                "Ada",
                "Aras",
                "Duru",
                "Ege",
                "Mavi",
                "Atlas",
                "Defne",
                "Yağız",
            ]
            for i, name in enumerate(names):
                s.add(
                    Participant(
                        id=f"{tid}-person-{i+1:02}",
                        name=f"{name} · Demo {i+1:02}",
                        title=role,
                        team_id=tid,
                        job_band="L3_L4",
                    )
                )


def seed_roles(store):
    with store.session() as s:
        for team in s.scalars(select(Team)):
            profile = s.scalar(
                select(RoleProfile).where(
                    RoleProfile.team_id == team.id, RoleProfile.is_default == True
                )
            )
            if not profile:
                profile = RoleProfile(
                    team_id=team.id,
                    title=team.role,
                    targets=team.targets,
                    is_default=True,
                )
                s.add(profile)
                s.flush()
            for p in s.scalars(
                select(Participant).where(Participant.team_id == team.id)
            ):
                if not s.get(ParticipantRole, p.id):
                    s.add(
                        ParticipantRole(participant_id=p.id, role_profile_id=profile.id)
                    )


def create_campaign(store, name, team_ids=None, participant_ids=None, language="en"):
    if language not in {"en", "tr"}:
        raise DomainError("invalid_language", "Language must be en or tr.")
    with store.session() as s:
        teams = (
            list(s.scalars(select(Team).where(Team.id.in_(team_ids))))
            if team_ids
            else list(s.scalars(select(Team)))
        )
        if not teams:
            raise DomainError("missing_teams", "Önce en az bir ekip oluşturun.")
        cfg = {
            "language": language,
            "team_snapshots": {
                t.id: {
                    "id": t.id,
                    "name": t.name,
                    "role": t.role,
                    "context": t.context,
                    "targets": t.targets,
                    "version": t.version,
                }
                for t in teams
            },
            "blueprint_version": "mixed-open-v1",
            "question_count": 22,
            "level_rule": "indicator-v1",
            "common_skills": COMMON,
        }
        profiles = list(
            s.scalars(
                select(RoleProfile).where(
                    RoleProfile.team_id.in_([t.id for t in teams])
                )
            )
        )
        if len(profiles) > 100:
            raise DomainError(
                "campaign_limit", "Bir dönemde en fazla 100 rol profili kullanılabilir."
            )
        cfg["role_snapshots"] = {
            r.id: {
                "id": r.id,
                "team_id": r.team_id,
                "title": r.title,
                "job_band": r.job_band,
                "targets": r.targets,
                "version": r.version,
            }
            for r in profiles
        }
        if participant_ids is not None:
            cfg["participant_ids"] = list(participant_ids)
            role_ids = set(
                s.scalars(
                    select(ParticipantRole.role_profile_id).where(
                        ParticipantRole.participant_id.in_(participant_ids)
                    )
                )
            )
            cfg["role_snapshots"] = {
                key: value
                for key, value in cfg["role_snapshots"].items()
                if key in role_ids
            }
        from .catalog import freeze_skills

        cfg["skill_snapshots"] = freeze_skills(s, cfg)
        campaign = Campaign(name=name, config=cfg)
        s.add(campaign)
        s.flush()
        return asdict(campaign)


def enqueue_generation(store, campaign_id):
    from .policies import policy

    instructions = policy(store)
    with store.session() as s:
        c = get(s, Campaign, campaign_id)
        if c.status != "draft":
            raise DomainError(
                "invalid_state",
                "Soru üretimi yalnızca taslak kampanyada başlatılır.",
                409,
            )
        if not c.config.get("skill_snapshots"):
            from .catalog import freeze_skills

            c.config = {**c.config, "skill_snapshots": freeze_skills(s, c.config)}
        profile = store.resolve("generation")
        job = s.scalar(select(Job).where(Job.dedupe_key == f"generate:{c.id}"))
        if job:
            job.status = "queued"
            job.attempts = 0
            job.available_at = 0
            job.error = None
            job.payload = {
                "campaign_id": c.id,
                "profile_version": profile["version_id"],
                "prompt_policy_id": instructions["id"],
            }
        else:
            job = Job(
                kind="generate",
                dedupe_key=f"generate:{c.id}",
                payload={
                    "campaign_id": c.id,
                    "profile_version": profile["version_id"],
                    "prompt_policy_id": instructions["id"],
                },
            )
            s.add(job)
        c.status = "preparing"
        s.flush()
        return asdict(job)


def example_questions(skills, team, language="tr"):
    if language == "en":
        from .language import english_examples

        return english_examples(skills, team)
    result = []
    for idx, skill in enumerate(skills):
        common = skill["id"] in COMMON
        scope = "common" if common else "role"
        context = (
            "Günlük bir iş kararında"
            if common
            else team["context"].get("purpose", team["role"])
        )
        for variant in range(2):
            rubric = []
            labels = [
                "Yöntem ve kavram doğruluğu",
                "Uygulama ve doğrulama",
                "Sınırlar ve risk yönetimi",
            ]
            for level, label in enumerate(labels, 1):
                descriptor = next(
                    (x["description"] for x in skill["levels"] if x["level"] == level),
                    "",
                )
                rubric.append(
                    {
                        "id": f"c{level}",
                        "label": label,
                        "level": level,
                        "indicator_id": f"{skill['id']}:L{level}",
                        "weight": 1,
                        "max_points": 4,
                        "descriptor": descriptor,
                        "anchors": {
                            "0": "Gösterge yok veya yanlış",
                            "1": "Kavramı anıyor, uygulama belirsiz",
                            "2": "Kısmen uygulanabilir, önemli eksik var",
                            "3": "Göstergeyi doğru ve uygulanabilir açıklıyor",
                            "4": "Alternatifleri, sınırları ve doğrulamayı somutlaştırıyor",
                        },
                    }
                )
            prompt = (
                f"{context}: {skill['name']} kapsamında AI çıktısında bir hata veya tutarsızlık fark ettiniz. Yaklaşımınızı, yapacağınız kontrolleri ve sonucu hangi koşullarda kullanacağınızı açıklayın."
                if variant == 0
                else f"{skill['name']} için yaşadığınız somut bir uygulamayı anlatın. Göreviniz, izlediğiniz adımlar, doğrulamanız ve sonuç neydi? Deneyiminiz yoksa belirtin ve nasıl ilerleyeceğinizi açıklayın."
            )
            result.append(
                {
                    "skill_id": skill["id"],
                    "type": "open_text",
                    "prompt": prompt,
                    "section": scope,
                    "options": [],
                    "rubric": rubric,
                    "reference": skill["definition"]
                    + "\n"
                    + "\n".join(r["descriptor"] for r in rubric),
                    "evidence_type": (
                        "scenario_reasoning"
                        if variant == 0
                        else "self_reported_experience"
                    ),
                }
            )
        if idx in [0, 2, 3, 5]:
            result.append(
                {
                    "skill_id": skill["id"],
                    "type": "single_choice",
                    "prompt": f"{skill['name']} sırasında AI tarafından üretilen, kararınızı etkileyen bir sonucu kullanmadan önce hangi yaklaşım daha uygundur?",
                    "section": scope,
                    "rubric": [],
                    "reference": "AI sonucu, özgün kaynak ve iş bağlamına uygun kontrollerle doğrulanır.",
                    "options": [
                        {
                            "id": "a",
                            "text": "İkna edici yazıldıysa doğrudan kullanmak",
                            "correct": False,
                        },
                        {
                            "id": "b",
                            "text": "Özgün kaynağı, varsayımları ve riskleri kontrol ederek doğrulamak",
                            "correct": True,
                        },
                        {
                            "id": "c",
                            "text": "Aynı yanıtı farklı kelimelerle yeniden üretmekle yetinmek",
                            "correct": False,
                        },
                        {"id": "d", "text": "Bilmiyorum", "correct": False},
                    ],
                }
            )
        result.append(
            {
                "skill_id": skill["id"],
                "type": "self_assessment",
                "prompt": f"{skill['name']} için mevcut deneyiminizi en iyi hangi ifade tanımlıyor?",
                "section": scope,
                "rubric": [],
                "reference": "",
                "options": [
                    {
                        "id": str(x["level"]),
                        "text": f"L{x['level']} · {x['label']} — {x['description']}",
                        "level": x["level"],
                    }
                    for x in skill["levels"]
                ]
                + [{"id": "none", "text": "Henüz deneyimim yok", "level": None}],
            }
        )
    return result


def generate_questions(store, job):
    from .policies import policy, DEFAULT_POLICY_ID

    instructions = policy(store, job.payload.get("prompt_policy_id", DEFAULT_POLICY_ID))
    with store.session() as s:
        c = get(s, Campaign, job.payload["campaign_id"])
        if c.status in ["content_review", "ready", "open", "closed"] and s.scalar(
            select(Question.id).where(Question.campaign_id == c.id).limit(1)
        ):
            return
        cfg = c.config
        catalog = {
            x.id: {
                "id": x.id,
                "name": x.name,
                "definition": x.definition,
                "levels": x.levels,
            }
            for x in s.scalars(select(Skill))
        }
    provider = Provider(
        store.resolve(version_id=job.payload["profile_version"]),
        store.settings.allowed_hosts,
        allowed_cidrs=store.settings.allowed_cidrs,
        ca_file=store.settings.llm_ca_file,
    )
    if cfg.get("skill_snapshots"):
        catalog = cfg["skill_snapshots"]
    generated = []
    seen_common = False
    profiles = list(cfg.get("role_snapshots", {}).values()) or [
        {"id": t["id"], "team_id": t["id"], "title": t["role"], "targets": t["targets"]}
        for t in cfg["team_snapshots"].values()
    ]
    for profile in profiles:
        team = {
            **cfg["team_snapshots"][profile["team_id"]],
            "role": profile["title"],
            "job_band": profile.get("job_band", ""),
            "role_profile_id": profile["id"],
            "targets": profile["targets"],
        }
        role = [
            x["skill_id"]
            for x in profile["targets"]
            if x["applicable"] and x["skill_id"] not in COMMON
        ][:3]
        if len(role) != 3:
            raise DomainError(
                "invalid_targets", "Bu blueprint için üç rol yetkinliği seçin."
            )
        skills = [catalog[x] for x in COMMON + role]
        language = cfg.get("language", "tr")
        examples = example_questions(skills, team, language)
        value, _ = provider.complete(
            "questions",
            {
                "language": language,
                "skills": skills,
                "team_context": team,
                "blueprint": {
                    "count": 22,
                    "open_text": 12,
                    "single_choice": 4,
                    "self_assessment": 6,
                },
                "example_questions": examples,
            },
            instructions=instructions["instructions"]["questions"],
        )
        from .validation import QuestionSet

        questions = QuestionSet.model_validate(value).model_dump()["questions"]
        if (
            len(questions) != 22
            or sum(q.get("type") == "open_text" for q in questions) != 12
        ):
            raise DomainError(
                "invalid_question_set", "Üretilen set blueprint ile eşleşmiyor."
            )
        counts = defaultdict(lambda: defaultdict(int))
        for q in questions:
            if (
                q.get("skill_id") not in COMMON + role
                or q.get("type")
                not in ["open_text", "single_choice", "self_assessment"]
                or not q.get("prompt")
            ):
                raise DomainError(
                    "invalid_question_set", "Soru türü/yetkinlik eşlemesi geçersiz."
                )
            counts[q["skill_id"]][q["type"]] += 1
            if q["type"] == "open_text":
                rub = q.get("rubric", [])
                if (
                    not rub
                    or len({r["id"] for r in rub}) != len(rub)
                    or any(
                        r.get("max_points", 4) != 4 or r.get("weight", 0) <= 0
                        for r in rub
                    )
                ):
                    raise DomainError("invalid_rubric", "Soru rubriği geçersiz.")
            if (
                q["type"] == "single_choice"
                and sum(bool(x.get("correct")) for x in q.get("options", [])) != 1
            ):
                raise DomainError(
                    "invalid_answer_key",
                    "Tek seçim sorusunda bir doğru seçenek gerekli.",
                )
            if len({o["id"] for o in q["options"]}) != len(q["options"]):
                raise DomainError(
                    "invalid_answer_key", "Seçenek kimlikleri benzersiz olmalı."
                )
            is_common = q["skill_id"] in COMMON
            if is_common and seen_common:
                continue
            generated.append(
                {
                    **q,
                    "form_key": "common" if is_common else profile["id"],
                    "section": "common" if is_common else "role",
                }
            )
        if any(
            counts[sid]["open_text"] != 2 or counts[sid]["self_assessment"] != 1
            for sid in COMMON + role
        ):
            raise DomainError(
                "invalid_coverage",
                "Her yetkinlik için iki açık uçlu ve bir öz değerlendirme gerekli.",
            )
        seen_common = True
    with store.session() as s:
        c = get(s, Campaign, job.payload["campaign_id"])
        if c.status != "preparing":
            raise DomainError(
                "invalid_state", "Kampanya soru hazırlama durumunda değil."
            )
        for i, q in enumerate(generated):
            s.add(
                Question(
                    campaign_id=c.id,
                    form_key=q["form_key"],
                    skill_id=q["skill_id"],
                    type=q["type"],
                    prompt=q["prompt"],
                    section=q["section"],
                    position=i,
                    options=q.get("options", []),
                    rubric=q.get("rubric", []),
                    reference=q.get("reference", "")
                    + (
                        "\nEXPERIENCE"
                        if q.get("evidence_type") == "self_reported_experience"
                        else ""
                    ),
                )
            )
        c.status = "content_review"
        c.row_version += 1
        c.config = {
            **c.config,
            "question_set_revision": 1,
            "question_approval": None,
            "generation_policy_id": instructions["id"],
            "generation_policy_version": instructions["version"],
        }
        s.add(
            Audit(
                action="questions_generated",
                entity_id=c.id,
                detail={
                    "count": len(generated),
                    "profile": job.payload["profile_version"],
                },
            )
        )


def campaign_transition(store, cid, action, expected_version=None, actor_id=None):
    with store.session() as s:
        c = get(s, Campaign, cid)
        if action in {"approve", "open"}:
            from .question_editor import (
                lock_campaign,
                validate_publication,
                form_hashes,
                set_counts,
            )

            c = lock_campaign(s, cid, expected_version)
            approved_questions = validate_publication(s, c)
        if action == "approve" and c.status in {"content_review", "ready"}:
            c.status = "ready"
            c.config = {
                **c.config,
                "question_counts": set_counts(c.config, approved_questions),
                "question_form_hashes": form_hashes(c.config, approved_questions),
                "question_approval": {
                    "revision": c.config.get("question_set_revision", 1),
                    "actor_id": actor_id,
                    "approved_at": now(),
                },
            }
            c.row_version += 1
        elif action == "open" and c.status == "ready":
            if (c.config.get("question_approval") or {}).get(
                "revision"
            ) != c.config.get("question_set_revision", 1):
                raise DomainError(
                    "question_approval_required",
                    "Güncel soru seti önce İK tarafından onaylanmalı.",
                    409,
                )
            questions = list(
                s.scalars(
                    select(Question)
                    .where(Question.campaign_id == cid)
                    .order_by(Question.position)
                )
            )
            for participant in s.scalars(
                select(Participant).where(
                    Participant.team_id.in_(list(c.config["team_snapshots"]))
                )
            ):
                if (
                    "participant_ids" in c.config
                    and participant.id not in c.config["participant_ids"]
                ):
                    continue
                team = c.config["team_snapshots"][participant.team_id]
                binding = s.get(ParticipantRole, participant.id)
                role = (
                    c.config.get("role_snapshots", {}).get(binding.role_profile_id)
                    if binding
                    else None
                )
                if c.config.get("role_snapshots") and not role:
                    raise DomainError(
                        "missing_role",
                        "Katılımcıya bu dönemde tanımlı bir rol profili atayın.",
                    )
                a = Assignment(
                    campaign_id=cid,
                    participant_id=participant.id,
                    profile_snapshot={
                        "participant_id": participant.id,
                        "name": participant.name,
                        "title": participant.title,
                        "job_band": participant.job_band,
                        "team": team,
                        "role_profile": role,
                    },
                )
                s.add(a)
                s.flush()
                selected = [
                    q
                    for q in questions
                    if q.form_key
                    in ["common", role["id"] if role else participant.team_id]
                ]
                for i, q in enumerate(selected):
                    s.add(
                        AssignedQuestion(
                            assignment_id=a.id, question_id=q.id, position=i
                        )
                    )
            c.status = "open"
            c.row_version += 1
        elif action == "close":
            changed = s.execute(
                update(Campaign)
                .where(Campaign.id == cid, Campaign.status == "open")
                .values(
                    status="closed",
                    closed_at=now(),
                    row_version=Campaign.row_version + 1,
                )
            )
            if not changed.rowcount:
                raise DomainError(
                    "invalid_state", "Yalnızca açık kampanya kapatılabilir.", 409
                )
            s.expire(c)
        else:
            raise DomainError(
                "invalid_state", "Bu kampanya durumunda işlem yapılamaz.", 409
            )
        s.add(
            Audit(
                action=f"campaign_{action}",
                entity_id=cid,
                detail={
                    "actor_id": actor_id,
                    "question_set_revision": c.config.get("question_set_revision", 1),
                },
            )
        )
        return asdict(c)


def latest_answers(s, aid):
    result = {}
    for a in s.scalars(
        select(Answer).where(Answer.assignment_id == aid).order_by(Answer.revision)
    ):
        result[a.question_id] = a
    return result


def form(store, aid):
    with store.session() as s:
        a = get(s, Assignment, aid)
        c = get(s, Campaign, a.campaign_id)
        rows = list(
            s.execute(
                select(AssignedQuestion, Question)
                .join(Question, Question.id == AssignedQuestion.question_id)
                .where(AssignedQuestion.assignment_id == aid)
                .order_by(AssignedQuestion.position)
            )
        )
        answers = latest_answers(s, aid)
        skills = {x.id: x.name for x in s.scalars(select(Skill))}
        skills.update(
            {
                sid: value["name"]
                for sid, value in c.config.get("skill_snapshots", {}).items()
            }
        )
        questions = []
        for aq, q in rows:
            answer = answers.get(q.id)
            questions.append(
                {
                    "id": q.id,
                    "type": q.type,
                    "prompt": q.prompt,
                    "section": q.section,
                    "skill_id": q.skill_id,
                    "skill_name": skills[q.skill_id],
                    "options": [
                        {k: v for k, v in o.items() if k not in ["correct", "level"]}
                        for o in q.options
                    ],
                    "answer": (
                        {
                            "text": answer.text,
                            "selected": answer.selected,
                            "state": answer.state,
                            "revision": answer.revision,
                            "saved_at": answer.saved_at,
                        }
                        if answer
                        else None
                    ),
                }
            )
        return {
            "assignment": asdict(a),
            "campaign": {"id": c.id, "name": c.name, "status": c.status},
            "questions": questions,
        }


def save_answer(store, aid, qid, payload):
    with store.session() as s:
        a = get(s, Assignment, aid)
        locked = s.execute(
            update(Campaign)
            .where(Campaign.id == a.campaign_id, Campaign.status == "open")
            .values(row_version=Campaign.row_version + 1)
        )
        if not locked.rowcount or a.status == "submitted":
            raise DomainError("form_locked", "Anket kapalı veya form gönderilmiş.", 409)
        if not s.scalar(
            select(AssignedQuestion.id).where(
                AssignedQuestion.assignment_id == aid,
                AssignedQuestion.question_id == qid,
            )
        ):
            raise DomainError("invalid_question", "Bu soru atanmış formda yok.", 404)
        q = get(s, Question, qid)
        previous = latest_answers(s, aid).get(qid)
        revision = previous.revision if previous else 0
        if revision != payload.get("revision", 0):
            raise DomainError(
                "revision_conflict",
                "Yanıt başka bir sekmede değişti. Formu yenileyin.",
                409,
            )
        value = payload.get("text", "")
        selected = payload.get("selected", [])
        if len(value) > 8000:
            raise DomainError("answer_too_long", "Yanıt 8.000 karakteri aşamaz.")
        if q.type == "open_text" and selected or q.type != "open_text" and value:
            raise DomainError("invalid_answer_type", "Yanıt türü soruyla eşleşmiyor.")
        if q.type != "open_text" and (
            len(selected) > 1
            or any(x not in {o["id"] for o in q.options} for x in selected)
        ):
            raise DomainError("invalid_option", "Seçenek bu soruya ait değil.")
        ans = Answer(
            assignment_id=aid,
            question_id=qid,
            revision=revision + 1,
            text=value,
            selected=selected,
            state=payload.get("state", "answered"),
        )
        s.add(ans)
        a.status = "draft"
        s.flush()
        return {"id": ans.id, "revision": ans.revision, "saved_at": ans.saved_at}


def submit(store, aid):
    from .quality import readable_text

    with store.session() as s:
        a = get(s, Assignment, aid)
        existing = s.scalar(select(Submission).where(Submission.assignment_id == aid))
        if existing:
            return {"id": existing.id, "status": "submitted"}
        lock = s.execute(
            update(Campaign)
            .where(Campaign.id == a.campaign_id, Campaign.status == "open")
            .values(row_version=Campaign.row_version + 1)
        )
        if not lock.rowcount:
            raise DomainError("campaign_closed", "Kampanya kapandı.", 409)
        answers = latest_answers(s, aid)
        expected = list(
            s.scalars(
                select(AssignedQuestion.question_id).where(
                    AssignedQuestion.assignment_id == aid
                )
            )
        )
        if not expected:
            raise DomainError("form_not_ready", "Form soruları henüz hazır değil.", 409)
        missing = [
            qid
            for qid in expected
            if qid not in answers
            or not (readable_text(answers[qid].text) or answers[qid].selected)
        ]
        if missing:
            raise DomainError(
                "incomplete_form",
                f"{len(missing)} soruyu yanıtlayın veya deneyiminiz olmadığını belirtin.",
            )
        submission = Submission(
            assignment_id=aid, answer_ids=[answers[q].id for q in expected]
        )
        s.add(submission)
        a.status = "submitted"
        a.submitted_at = now()
        s.flush()
        return {"id": submission.id, "status": "submitted"}


def start_run(store, cid):
    from .policies import policy

    instructions = policy(store)
    with store.session() as s:
        c = get(s, Campaign, cid)
        if c.status != "closed":
            raise DomainError(
                "campaign_not_closed", "Önce anket kampanyasını kapatın.", 409
            )
        existing = s.scalar(
            select(Run).where(
                Run.campaign_id == cid,
                Run.status.in_(["queued", "evaluating", "validating"]),
            )
        )
        if existing:
            return asdict(existing)
        subs = list(
            s.scalars(
                select(Submission)
                .join(Assignment, Assignment.id == Submission.assignment_id)
                .where(Assignment.campaign_id == cid)
            )
        )
        if not subs:
            raise DomainError(
                "no_submissions", "Değerlendirilecek gönderim bulunmuyor."
            )
        manifest = sorted([aid for sub in subs for aid in sub.answer_ids])
        profile = store.resolve("evaluation")
        insight = store.resolve("insights")
        r = Run(
            campaign_id=cid,
            input_manifest=manifest,
            input_hash=hashlib.sha256(json.dumps(manifest).encode()).hexdigest(),
            profile_version=profile["version_id"],
            insight_profile_version=insight["version_id"],
        )
        s.add(r)
        s.flush()
        s.add(
            RunPolicy(
                run_id=r.id,
                policy_id=instructions["id"],
                version=instructions["version"],
            )
        )
        for answer in s.scalars(select(Answer).where(Answer.id.in_(manifest))):
            q = get(s, Question, answer.question_id)
            if q.type == "open_text":
                s.add(
                    Job(
                        run_id=r.id,
                        kind="grade",
                        dedupe_key=f"{r.id}:{answer.id}:primary",
                        payload={
                            "answer_id": answer.id,
                            "profile_version": r.profile_version,
                            "pass_no": 1,
                            "prompt_policy_id": instructions["id"],
                        },
                    )
                )
                if (
                    int(hashlib.sha256(answer.id.encode()).hexdigest()[:4], 16) % 10
                    == 0
                ):
                    s.add(
                        Job(
                            run_id=r.id,
                            kind="grade",
                            dedupe_key=f"{r.id}:{answer.id}:secondary",
                            payload={
                                "answer_id": answer.id,
                                "profile_version": r.profile_version,
                                "pass_no": 2,
                                "prompt_policy_id": instructions["id"],
                            },
                        )
                    )
        return asdict(r)


def assignments(store, cid):
    with store.session() as s:
        return [
            {
                **asdict(a),
                "name": p.name,
                "title": p.title,
                "team_name": a.profile_snapshot["team"]["name"],
            }
            for a, p in s.execute(
                select(Assignment, Participant)
                .join(Participant)
                .where(Assignment.campaign_id == cid)
                .order_by(Participant.name)
            )
        ]


def seed_answers(store, cid, count=24):
    for index, a in enumerate(assignments(store, cid)[:count]):
        current = form(store, a["id"])
        for q in current["questions"]:
            if q["type"] == "open_text":
                value = f"Önce iş amacını ve veri kaynağını belirlerim. {q['skill_name']} için kaynak veriyi ve varsayımları kontrol eder, örneklem üzerinde karşılaştırma yaparım. Riskleri ve belirsizliği kaydeder, sonuçları bağımsız bir yöntemle doğrularım. Demo senaryo {index+1}."
                save_answer(
                    store,
                    a["id"],
                    q["id"],
                    {
                        "text": value,
                        "revision": q["answer"]["revision"] if q["answer"] else 0,
                    },
                )
            else:
                option = (
                    str(index % 3 + 1)
                    if q["type"] == "self_assessment"
                    else ("a" if index % 4 == 0 else "b")
                )
                save_answer(
                    store,
                    a["id"],
                    q["id"],
                    {
                        "selected": [option],
                        "revision": q["answer"]["revision"] if q["answer"] else 0,
                    },
                )
        submit(store, a["id"])

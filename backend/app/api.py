import json
import time
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request, UploadFile, File, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, update, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.exceptions import RequestValidationError
from .config import Settings, ROOT, REFERENCE_DIR
from .store import Store, DomainError, get, engine_for
from .models import *
from .services import *
from .reporting import metrics, publish
from .providers import Provider
from .audit import correlation_context
from .validation import (
    TeamInput,
    RoleInput,
    PersonInput,
    BindingInput,
    ActivateInput,
    ExportInput,
)
from .security import AuthService, install_auth, current_actor
from .access import (
    require_business,
    require_manager,
    require_hr,
    require_integrations,
    visible_team_ids,
    team_control,
    check_team,
    check_campaign,
    campaign_control,
    campaign_people,
    check_assignment,
    filter_snapshot,
    check_export,
)


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    config: dict
    secret: str | None = Field(default=None, max_length=4096)
    clear_secret: bool = False


class CampaignInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    team_ids: list[str] | None = Field(default=None, max_length=100)


class AnswerInput(BaseModel):
    text: str = Field(default="", max_length=8000)
    selected: list[str] = Field(default_factory=list, max_length=20)
    state: str = "answered"
    revision: int = Field(default=0, ge=0)


class ReviewInput(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
    score: float | None = Field(default=None, ge=0, le=100)


def create_app(settings=None, store=None, auth_service=None):
    store = store or Store(settings or Settings.from_env())
    store.settings.validate_web()
    app = FastAPI(
        title="Aptilume · AI Skills Intelligence",
        version="0.3.1",
        docs_url="/docs" if store.settings.demo else None,
        openapi_url="/openapi.json" if store.settings.demo else None,
        redoc_url=None,
    )
    app.state.store = store
    app.state.auth = auth_service or AuthService(store)
    install_auth(app, store, app.state.auth)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "code": "invalid_request",
                "message": "Alanların türünü, boyutunu ve zorunlu değerlerini kontrol edin.",
                "errors": [
                    {
                        "field": ".".join(str(x)[:50] for x in error["loc"][:6]),
                        "type": error["type"],
                    }
                    for error in exc.errors()[:20]
                ],
            },
        )

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        from .audit import record

        record(
            store,
            "operation_denied",
            "denied",
            actor_id=getattr(getattr(request.state, "actor", None), "id", ""),
            reason=exc.code,
            status=exc.status,
        )
        return JSONResponse(
            status_code=exc.status,
            content={
                "code": exc.code,
                "message": exc.message,
                "correlation_id": correlation_context.get(),
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def unavailable_database(request, exc):
        return JSONResponse(
            status_code=503,
            content={
                "code": "application_store_unavailable",
                "message": "Veri deposuna ulaşılamadı. Bağlantı ayarlarını kontrol edin; kayıt tamamlanmadı.",
                "correlation_id": correlation_context.get(),
            },
        )

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    @app.get("/health/startup")
    def ready():
        with store.control.connect() as c:
            c.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "mode": "demo" if store.settings.demo else "configured",
        }

    @app.get("/health/application")
    def application_health():
        try:
            with store.engine.connect() as c:
                c.execute(select(Campaign.id).limit(1))
            return {"status": "ready"}
        except Exception:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "degraded",
                    "message": "Admin bağlantı ayarlarını kontrol edin.",
                },
            )

    @app.get("/api/v1/bootstrap")
    def bootstrap():
        actor = current_actor()
        if not actor.business:
            return {
                "product": "Aptilume",
                "tagline": "AI Skills Intelligence",
                "identity": actor.public(),
                "security": {"offline_database_migration": not store.settings.demo},
                "teams": [],
                "participants": [],
                "role_profiles": [],
                "editable_team_ids": [],
                "campaigns": [],
                "skills_count": 0,
                "source_issues": [],
            }
        try:
            return bootstrap_data()
        except (SQLAlchemyError, DomainError):
            return {
                "product": "Aptilume",
                "tagline": "AI Skills Intelligence",
                "identity": current_actor().public(),
                "security": {"offline_database_migration": not store.settings.demo},
                "mode": "demo",
                "teams": [],
                "role_profiles": [],
                "editable_team_ids": [],
                "participants": [],
                "campaigns": [],
                "skills_count": 0,
                "source_issues": [],
                "degraded": True,
                "message": "Uygulama DB’sine ulaşılamıyor. Bağlantı ayarlarından düzeltebilirsiniz.",
            }

    def bootstrap_data():
        actor = current_actor()
        with store.session() as s:
            team_ids = visible_team_ids(s, actor) if actor.business else set()
            allowed_people = (
                list(s.scalars(select(Participant)))
                if actor.hr
                else list(
                    s.scalars(
                        select(Participant).where(
                            Participant.id.in_(list(actor.participant_ids or []))
                        )
                    )
                )
            )
            role_bindings = {
                x.participant_id: x.role_profile_id
                for x in s.scalars(select(ParticipantRole))
            }
            return {
                "product": "Aptilume",
                "tagline": "AI Skills Intelligence",
                "identity": actor.public(),
                "security": {"offline_database_migration": not store.settings.demo},
                "teams": [
                    asdict(t)
                    for t in s.scalars(select(Team).where(Team.id.in_(list(team_ids))))
                ],
                "editable_team_ids": [
                    tid for tid in team_ids if team_control(s, tid, actor)
                ],
                "role_profiles": [
                    asdict(r)
                    for r in s.scalars(select(RoleProfile))
                    if actor.hr
                    or r.id in {role_bindings.get(p.id) for p in allowed_people}
                ],
                "participants": [
                    {**asdict(p), "role_profile_id": role_bindings.get(p.id)}
                    for p in allowed_people
                ],
                "campaigns": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "status": c.status,
                        "created_at": c.created_at,
                        "publication_id": c.publication_id,
                        "can_manage": campaign_control(s, c, actor),
                        "assigned": len(
                            list(
                                s.scalars(
                                    select(Assignment.id).where(
                                        Assignment.campaign_id == c.id,
                                        *(
                                            ()
                                            if actor.hr
                                            else (
                                                Assignment.participant_id.in_(
                                                    list(actor.participant_ids or [])
                                                ),
                                            )
                                        ),
                                    )
                                )
                            )
                        ),
                        "submitted": len(
                            list(
                                s.scalars(
                                    select(Assignment.id).where(
                                        Assignment.campaign_id == c.id,
                                        Assignment.status == "submitted",
                                        *(
                                            ()
                                            if actor.hr
                                            else (
                                                Assignment.participant_id.in_(
                                                    list(actor.participant_ids or [])
                                                ),
                                            )
                                        ),
                                    )
                                )
                            )
                        ),
                    }
                    for c in s.scalars(
                        select(Campaign).order_by(Campaign.created_at.desc())
                    )
                    if actor.business
                    and (
                        actor.hr
                        or campaign_people(s, c).intersection(
                            actor.participant_ids or ()
                        )
                    )
                ],
                "skills_count": len(list(s.scalars(select(Skill.id)))),
                "source_issues": (
                    json.loads((REFERENCE_DIR / "catalog.json").read_text())[
                        "import_issues"
                    ]
                    if actor.hr
                    else []
                ),
            }

    @app.get("/api/v1/skills")
    def skills():
        with store.session() as s:
            return [
                {
                    "id": x.id,
                    "code": x.code,
                    "name": x.name,
                    "definition": x.definition,
                    "levels": x.levels,
                    "owners": x.metadata_.get("owners", []),
                }
                for x in s.scalars(select(Skill).order_by(Skill.code))
            ]

    @app.post("/api/v1/catalog/import")
    def import_bundled():
        return load_catalog(store)

    @app.post("/api/v1/teams")
    def add_team(value: TeamInput):
        payload = value.model_dump()
        validate_team(payload)
        with store.session() as s:
            t = Team(
                name=payload["name"],
                role=payload["role"],
                context=payload.get("context", {}),
                targets=payload["targets"],
            )
            s.add(t)
            s.flush()
            return asdict(t)

    @app.patch("/api/v1/teams/{tid}")
    def patch_team(tid: str, value: TeamInput):
        payload = value.model_dump()
        with store.session() as s:
            check_team(s, tid, write=True)
            validate_team(payload)
            t = get(s, Team, tid)
            t.name = payload["name"]
            t.role = payload["role"]
            t.context = payload.get("context", {})
            t.targets = payload["targets"]
            t.version += 1
            for role in s.scalars(
                select(RoleProfile).where(
                    RoleProfile.team_id == tid, RoleProfile.is_default == True
                )
            ):
                role.title = t.role
                role.targets = t.targets
                role.version += 1
            return asdict(t)

    def validate_team(p):
        if not p.get("name") or not p.get("role"):
            raise DomainError("invalid_team", "Ekip adı ve rol gerekli.")
        with store.session() as s:
            ids = {x for x in s.scalars(select(Skill.id))}
        if any(
            x.get("skill_id") not in ids
            or x.get("target_level") not in range(1, 6)
            or x.get("criticality") not in range(1, 6)
            for x in p.get("targets", [])
        ):
            raise DomainError(
                "invalid_targets", "Yetkinlik, hedef ve önem alanlarını kontrol edin."
            )
        if len({x["skill_id"] for x in p.get("targets", [])}) != len(
            p.get("targets", [])
        ):
            raise DomainError("duplicate_targets", "Aynı yetkinlik tekrarlanamaz.")

    @app.post("/api/v1/role-profiles")
    def add_role(value: RoleInput):
        p = value.model_dump()
        validate_team(
            {
                "name": p.get("title"),
                "role": p.get("title"),
                "targets": p.get("targets", []),
            }
        )
        with store.session() as s:
            check_team(s, p["team_id"], write=True)
            get(s, Team, p["team_id"])
            r = RoleProfile(
                team_id=p["team_id"],
                title=p["title"],
                job_band=p.get("job_band", "L3_L4"),
                targets=p["targets"],
            )
            s.add(r)
            s.flush()
            return asdict(r)

    @app.patch("/api/v1/role-profiles/{rid}")
    def edit_role(rid: str, value: RoleInput):
        p = value.model_dump()
        validate_team(
            {
                "name": p.get("title"),
                "role": p.get("title"),
                "targets": p.get("targets", []),
            }
        )
        with store.session() as s:
            r = get(s, RoleProfile, rid)
            check_team(s, r.team_id, write=True)
            r.title = p["title"]
            r.job_band = p.get("job_band", r.job_band)
            r.targets = p["targets"]
            r.version += 1
            return asdict(r)

    @app.post("/api/v1/participants")
    def add_participant(p: PersonInput):
        return save_participant(p.model_dump())

    @app.patch("/api/v1/participants/{pid}")
    def edit_participant(pid: str, p: PersonInput):
        return save_participant(p.model_dump(), pid)

    def save_participant(p, pid=None):
        if not p.get("name") or not p.get("title"):
            raise DomainError("invalid_participant", "Ad ve title gerekli.")
        with store.session() as s:
            role = get(s, RoleProfile, p["role_profile_id"])
            person = get(s, Participant, pid) if pid else Participant(id=uid())
            person.name = p["name"]
            person.title = p["title"]
            person.team_id = role.team_id
            person.job_band = p.get("job_band", role.job_band)
            if not pid:
                s.add(person)
                s.flush()
            binding = s.get(ParticipantRole, person.id)
            if binding:
                binding.role_profile_id = role.id
            else:
                s.add(
                    ParticipantRole(participant_id=person.id, role_profile_id=role.id)
                )
            return asdict(person)

    @app.post("/api/v1/campaigns")
    def new_campaign(p: CampaignInput):
        actor = require_manager()
        if actor.hr:
            return create_campaign(store, p.name, p.team_ids)
        with store.session() as s:
            allowed = visible_team_ids(s, actor)
            selected = set(p.team_ids) if p.team_ids else allowed
            if not selected or not selected.issubset(allowed):
                raise DomainError(
                    "forbidden",
                    "Yalnızca kendi ekipleriniz için dönem oluşturabilirsiniz.",
                    403,
                )
            people = [
                pid
                for pid in s.scalars(
                    select(Participant.id).where(
                        Participant.team_id.in_(list(selected))
                    )
                )
                if actor.sees(pid)
            ]
        return create_campaign(store, p.name, list(selected), participant_ids=people)

    @app.post("/api/v1/campaigns/{cid}/generate-questions", status_code=202)
    def generate(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
        return enqueue_generation(store, cid)

    @app.get("/api/v1/campaigns/{cid}/questions")
    def questions(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
            return [
                asdict(q)
                for q in s.scalars(
                    select(Question)
                    .where(Question.campaign_id == cid)
                    .order_by(Question.position)
                )
            ]

    @app.post("/api/v1/campaigns/{cid}/approve")
    def approve_campaign(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
        return campaign_transition(store, cid, "approve")

    @app.post("/api/v1/campaigns/{cid}/open")
    def open_campaign(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
        return campaign_transition(store, cid, "open")

    @app.post("/api/v1/campaigns/{cid}/close")
    def close_campaign(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
        return campaign_transition(store, cid, "close")

    @app.get("/api/v1/campaigns/{cid}/assignments")
    def campaign_assignments(cid: str):
        with store.session() as s:
            check_campaign(s, cid)
        actor = current_actor()
        return [a for a in assignments(store, cid) if actor.sees(a["participant_id"])]

    @app.get("/api/v1/assignments/{aid}/form")
    def assignment_form(aid: str):
        with store.session() as s:
            check_assignment(s, aid)
        result = form(store, aid)
        result["can_answer"] = (
            result["assignment"]["participant_id"] == current_actor().participant_id
        )
        return result

    @app.put("/api/v1/assignments/{aid}/answers/{qid}")
    def answer(aid: str, qid: str, p: AnswerInput):
        with store.session() as s:
            check_assignment(s, aid, write=True)
        return save_answer(store, aid, qid, p.model_dump())

    @app.post("/api/v1/assignments/{aid}/submit")
    def submit_form(aid: str):
        with store.session() as s:
            check_assignment(s, aid, write=True)
        return submit(store, aid)

    @app.post("/api/v1/campaigns/{cid}/evaluation-runs", status_code=202)
    def evaluate(cid: str):
        with store.session() as s:
            check_campaign(s, cid, write=True)
        return start_run(store, cid)

    @app.get("/api/v1/evaluation-runs")
    def runs():
        with store.session() as s:
            return [
                run_view(s, r)
                for r in s.scalars(select(Run).order_by(Run.created_at.desc()))
                if current_actor().hr
                or campaign_people(s, get(s, Campaign, r.campaign_id)).intersection(
                    current_actor().participant_ids or ()
                )
            ]

    def run_view(s, r):
        jobs = list(s.scalars(select(Job).where(Job.run_id == r.id)))
        actor = current_actor()
        campaign = get(s, Campaign, r.campaign_id)
        allowed_answers = (
            set(
                s.scalars(
                    select(Answer.id)
                    .join(Assignment, Assignment.id == Answer.assignment_id)
                    .where(
                        Assignment.participant_id.in_(list(actor.participant_ids or []))
                    )
                )
            )
            if not actor.hr
            else None
        )
        if allowed_answers is not None:
            jobs = [j for j in jobs if j.payload.get("answer_id") in allowed_answers]
        counts = {
            status: sum(j.status == status for j in jobs)
            for status in ["queued", "running", "done", "failed", "cancelled"]
        }
        calls = list(
            s.scalars(select(Call).where(Call.job_id.in_([j.id for j in jobs])))
        )
        return {
            **{
                k: v
                for k, v in asdict(r).items()
                if k
                in ["id", "campaign_id", "status", "created_at", "finished_at", "error"]
            },
            "campaign_name": campaign.name,
            "can_manage": campaign_control(s, campaign, actor),
            "jobs": counts,
            "total": len(jobs),
            "progress": round(100 * counts["done"] / len(jobs)) if jobs else 0,
            "calls": len(calls),
            "reviews": len(
                list(
                    s.scalars(
                        select(Evaluation.id).where(
                            Evaluation.run_id == r.id,
                            Evaluation.review_status == "pending",
                            *(
                                ()
                                if actor.hr
                                else (Evaluation.answer_id.in_(list(allowed_answers)),)
                            ),
                        )
                    )
                )
            ),
        }

    @app.get("/api/v1/evaluation-runs/{rid}/reviews")
    def reviews(rid: str):
        with store.session() as s:
            check_campaign(s, get(s, Run, rid).campaign_id)
            result = []
            for e in s.scalars(
                select(Evaluation).where(
                    Evaluation.run_id == rid, Evaluation.review_status == "pending"
                )
            ):
                a = get(s, Answer, e.answer_id)
                if not current_actor().sees(
                    get(s, Assignment, a.assignment_id).participant_id
                ):
                    continue
                q = get(s, Question, a.question_id)
                result.append(
                    {
                        **asdict(e),
                        "answer": a.text,
                        "question": q.prompt,
                        "rubric": q.rubric,
                        "can_review": get(s, Assignment, a.assignment_id).participant_id
                        != current_actor().participant_id,
                    }
                )
            return result

    @app.post("/api/v1/reviews/{eid}/decision")
    def review(eid: str, p: ReviewInput):
        with store.session() as s:
            e = get(s, Evaluation, eid)
            answer = get(s, Answer, e.answer_id)
            check_assignment(s, answer.assignment_id)
            if (
                get(s, Assignment, answer.assignment_id).participant_id
                == current_actor().participant_id
            ):
                raise DomainError(
                    "self_review_forbidden",
                    "Kendi yanıtınızı inceleyemezsiniz. Başka bir yetkili incelemeli.",
                    403,
                )
            r = get(s, Run, e.run_id)
            if r.status == "published":
                raise DomainError(
                    "published_result",
                    "Yayımlanan sonucu değiştirmek için yeni koşu açın.",
                    409,
                )
            changed = s.execute(
                update(Evaluation)
                .where(Evaluation.id == eid, Evaluation.review_status == "pending")
                .values(review_status="resolved")
            )
            if changed.rowcount != 1:
                raise DomainError(
                    "review_conflict",
                    "İnceleme bekleyen durumda değil veya başka bir yetkili tarafından tamamlandı.",
                    409,
                )
            s.add(
                ReviewDecision(
                    evaluation_id=eid,
                    score=p.score,
                    reason=p.reason,
                    reviewer=current_actor().id,
                )
            )
            e.review_status = "resolved"
            rid = e.run_id
        from .worker import Worker

        Worker(store).finalize(rid)
        return {"status": "resolved"}

    @app.post("/api/v1/evaluation-runs/{rid}/retry-failed")
    def retry(rid: str):
        with store.session() as s:
            r = get(s, Run, rid)
            check_campaign(s, r.campaign_id, write=True)
            if r.status == "published":
                raise DomainError(
                    "published_result", "Yayımlanmış koşu yeniden yazılamaz.", 409
                )
            s.execute(
                update(Job)
                .where(Job.run_id == rid, Job.status == "failed")
                .values(status="queued", attempts=0, available_at=0, error=None)
            )
            r.status = "queued"
            r.error = None
        return {"status": "queued"}

    @app.post("/api/v1/evaluation-runs/{rid}/cancel")
    def cancel(rid: str):
        with store.session() as s:
            r = get(s, Run, rid)
            check_campaign(s, r.campaign_id, write=True)
            if r.status == "published":
                raise DomainError(
                    "published_result", "Yayımlanmış koşu iptal edilemez.", 409
                )
            r.status = "cancelled"
            s.execute(
                update(Job)
                .where(Job.run_id == rid, Job.status == "queued")
                .values(status="cancelled")
            )
        return {"status": "cancelled"}

    @app.post("/api/v1/evaluation-runs/{rid}/publish")
    def publication(rid: str):
        with store.session() as s:
            check_campaign(s, get(s, Run, rid).campaign_id, write=True)
        return {"publication_id": publish(store, rid)}

    @app.get("/api/v1/reports/{pid}")
    def report(pid: str, team_id: str | None = None, skill_id: str | None = None):
        with store.session() as s:
            actor = require_business()
            publication = get(s, Publication, pid)
            check_campaign(s, publication.campaign_id)
            snapshot = filter_snapshot(s, publication.snapshot)
            if team_id and team_id not in {
                a["team_id"] for a in snapshot["assignments"]
            }:
                raise DomainError("not_found", "Ekip bulunamadı.", 404)
            result = metrics(snapshot, team_id, skill_id)
            result["report_info"] = {
                "publication_id": pid,
                "published_at": publication.published_at,
                "version": publication.version,
                "source": "simulation" if snapshot["mock"] else "llm",
                "scoring_version": snapshot["scoring_version"],
                "scope": (
                    "organization"
                    if actor.hr
                    else "my_teams" if actor.manager else "self"
                ),
            }
            return result

    @app.get("/api/v1/jobs")
    def jobs():
        with store.session() as s:
            return [
                asdict(j)
                for j in s.scalars(
                    select(Job).order_by(Job.created_at.desc()).limit(100)
                )
            ]

    @app.get("/api/v1/admin/connections/{kind}")
    def profiles(kind: str):
        return store.profiles(kind)

    @app.post("/api/v1/admin/connections/{kind}")
    def add_profile(kind: str, p: ProfileInput):
        return store.save_profile(kind, p.name, p.config, p.secret)

    @app.patch("/api/v1/admin/connections/{kind}/{pid}")
    def edit_profile(kind: str, pid: str, p: ProfileInput):
        return store.save_profile(kind, p.name, p.config, p.secret, pid, p.clear_secret)

    @app.delete("/api/v1/admin/connections/{kind}/{pid}")
    def delete_profile(kind: str, pid: str):
        store.delete_profile(pid)
        return {"status": "deleted"}

    @app.put("/api/v1/admin/service-bindings/{purpose}")
    def bind(purpose: str, p: BindingInput):
        require_hr()
        store.bind(purpose, p.profile_id)
        return {"status": "active"}

    @app.post("/api/v1/admin/connections/{kind}/{pid}/test")
    def test_profile(kind: str, pid: str):
        p = next((x for x in store.profiles(kind) if x["id"] == pid), None)
        if not p:
            raise DomainError("not_found", "Profil bulunamadı.", 404)
        cfg = store.resolve(version_id=f"{pid}:{p['version']}")
        start = time.monotonic()
        try:
            if kind == "llm":
                result, _ = Provider(
                    cfg,
                    store.settings.allowed_hosts,
                    allowed_cidrs=store.settings.allowed_cidrs,
                    ca_file=store.settings.llm_ca_file,
                ).complete("test", {"test": "connectivity_only"})
                if result.get("ok") is not True:
                    raise ValueError("unexpected_schema")
                mode = "mock" if cfg["provider"] == "mock" else "real"
            else:
                db_config = {
                    k: v for k, v in cfg.items() if k not in ["secret", "version_id"]
                }
                engine = engine_for(
                    store.db_url(db_config, cfg.get("secret"), connect=True)
                )
                try:
                    with engine.connect() as c:
                        c.execute(text("SELECT 1"))
                finally:
                    engine.dispose()
                mode = "real"
            return {
                "status": "success",
                "mode": mode,
                "message": (
                    "Simülasyon başarılı"
                    if mode == "mock"
                    else "Bağlantı doğrulandı; kalite testi ayrı yapılır."
                ),
                "latency_ms": round((time.monotonic() - start) * 1000, 1),
            }
        except Exception as e:
            return {
                "status": "failed",
                "mode": "mock" if cfg.get("provider") == "mock" else "real",
                "message": (
                    e.message
                    if isinstance(e, DomainError)
                    else "Bağlantı kurulamadı. Endpoint, kimlik bilgileri ve ağ ayarlarını kontrol edin."
                ),
                "error_type": type(e).__name__,
            }

    @app.post("/api/v1/admin/db-connections/{pid}/migration-preview")
    def migration_preview(pid: str):
        require_hr()
        with store.session() as s:
            return {
                "maintenance_required": True,
                "open_campaigns": len(
                    list(
                        s.scalars(select(Campaign.id).where(Campaign.status == "open"))
                    )
                ),
                "records": {
                    t.name: s.execute(select(t)).fetchall().__len__()
                    for t in Base.metadata.sorted_tables
                },
                "target_profile": pid,
                "copy_existing_default": True,
            }

    @app.post("/api/v1/admin/db-connections/{pid}/activate")
    def activate(pid: str, p: ActivateInput):
        require_hr()
        return store.activate_db(pid, p.copy_existing)

    @app.post("/api/v1/exports", status_code=202)
    def export(value: ExportInput):
        p = value.model_dump()
        with store.session() as s:
            actor = require_business()
            publication = get(s, Publication, p["publication_id"])
            check_campaign(s, publication.campaign_id)
            filters = {
                k: v
                for k, v in p.get("filters", {}).items()
                if k in ["team_id", "skill_id"]
            }
            snapshot = filter_snapshot(s, publication.snapshot)
            if filters.get("team_id") and filters["team_id"] not in {
                a["team_id"] for a in snapshot["assignments"]
            }:
                raise DomainError("not_found", "Ekip bulunamadı.", 404)
            e = Export(
                publication_id=p["publication_id"],
                filters=filters,
                detail=bool(p.get("detail")),
            )
            s.add(e)
            s.flush()
            s.add(
                ExportScope(
                    export_id=e.id,
                    creator_id=actor.id,
                    participant_ids=(
                        None if actor.hr else list(actor.participant_ids or [])
                    ),
                )
            )
            s.add(
                Job(
                    kind="export",
                    dedupe_key=f"export:{e.id}",
                    payload={"export_id": e.id},
                )
            )
            return asdict(e)

    @app.get("/api/v1/exports")
    def exports():
        with store.session() as s:
            return [
                {k: v for k, v in asdict(e).items() if k != "file"}
                for e in s.scalars(select(Export).order_by(Export.created_at.desc()))
                if current_actor().hr
                or (
                    s.get(ExportScope, e.id)
                    and s.get(ExportScope, e.id).creator_id == current_actor().id
                    and s.get(ExportScope, e.id).participant_ids is not None
                    and set(s.get(ExportScope, e.id).participant_ids).issubset(
                        current_actor().participant_ids or ()
                    )
                )
            ]

    @app.get("/api/v1/exports/{eid}/download")
    def download(eid: str):
        with store.session() as s:
            e = get(s, Export, eid)
            check_export(s, e)
            if e.status != "ready":
                raise DomainError("not_ready", "Excel henüz hazır değil.", 409)
            from .exports import artifact_path

            path = artifact_path(store, e)
            from .audit import record

            record(
                store, "export_downloaded", actor_id=current_actor().id, target_id=eid
            )
            return FileResponse(
                path,
                filename=f"Aptilume-{eid[:8]}.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    from .product import install_product_routes

    install_product_routes(app, store)
    from .http_security import SecurityEnvelope

    app.add_middleware(SecurityEnvelope, store=store)
    dist = ROOT / "web/dist"
    if dist.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        app.mount("/brand", StaticFiles(directory=dist / "brand"), name="brand")

        @app.get("/{path:path}")
        def spa(path: str):
            if path.startswith(("api/", "health/")) or path in {
                "docs",
                "redoc",
                "openapi.json",
            }:
                raise DomainError("not_found", "Adres bulunamadı.", 404)
            return FileResponse(dist / "index.html")

    return app

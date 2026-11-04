from datetime import date
from fastapi import Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from .models import *
from .store import get, DomainError
from .services import asdict
from .security import current_actor
from .access import (
    require_business,
    require_manager,
    require_integrations,
    require_hr,
    check_team,
    team_control,
    filter_snapshot,
)
from .directory import (
    directory_config,
    propose_directory_change,
    approve_directory_change,
    public_change,
    directory_protected,
)
from .reporting import metrics


class ActionInput(BaseModel):
    title: str = Field(min_length=3, max_length=250)
    owner_name: str = Field(min_length=2, max_length=200)
    publication_id: str | None = None
    team_id: str | None = None
    participant_id: str | None = None
    skill_id: str | None = None
    due_date: date | None = None
    status: str = "planned"
    notes: str = Field(default="", max_length=8000)
    row_version: int = 1


def workspace(store):
    with store.cs() as s:
        row = s.get(Setting, "workspace")
        return (
            row.value
            if row
            else {"name": "Yapı Kredi Teknoloji", "timezone": "Europe/Istanbul"}
        )


def action_visible(s, item, actor):
    if actor.hr:
        return True
    if item.participant_id:
        return actor.sees(item.participant_id)
    return bool(item.team_id and team_control(s, item.team_id, actor))


def install_product_routes(app, store):
    @app.get("/api/v1/settings/workspace")
    def get_workspace():
        return workspace(store)

    @app.put("/api/v1/settings/workspace")
    def save_workspace(p: dict):
        actor = require_integrations()
        name = str(p.get("name", "")).strip()
        if not 2 <= len(name) <= 150:
            raise DomainError(
                "invalid_workspace", "Çalışma alanı adı 2–150 karakter olmalı."
            )
        value = {"name": name, "timezone": "Europe/Istanbul"}
        with store.cs() as s:
            row = s.get(Setting, "workspace")
            if row:
                row.value = value
            else:
                s.add(Setting(key="workspace", value=value))
            s.add(
                ControlEvent(
                    profile_id=actor.id,
                    action="workspace_updated",
                    detail={"name": name},
                )
            )
        return value

    @app.get("/api/v1/admin/directory")
    def directory():
        config = directory_config(store)
        with store.cs() as s:
            state = s.get(Setting, "directory_sync")
            config["sync_status"] = state.value if state else {"last_sync": 0}
            pending = s.scalar(
                select(DirectoryChange)
                .where(DirectoryChange.status == "pending")
                .order_by(DirectoryChange.created_at.desc())
                .limit(1)
            )
            config["pending_change"] = public_change(pending) if pending else None
        config["approval_required"] = (
            directory_protected(store) and not current_actor().hr
        )
        config["can_approve"] = current_actor().hr
        return config

    @app.put("/api/v1/admin/directory")
    def save_directory(p: dict):
        return propose_directory_change(store, p, require_integrations())

    @app.post("/api/v1/admin/directory/changes/{change_id}/approve")
    def approve_directory(change_id: str):
        return approve_directory_change(store, change_id, require_hr())

    @app.post("/api/v1/admin/directory/changes/{change_id}/reject")
    def reject_directory(change_id: str):
        actor = require_hr()
        with store.cs() as s:
            changed = s.execute(
                update(DirectoryChange)
                .where(
                    DirectoryChange.id == change_id, DirectoryChange.status == "pending"
                )
                .values(status="rejected", approved_by=actor.id)
            )
            if changed.rowcount != 1:
                raise DomainError(
                    "change_conflict", "Değişiklik bekleyen durumda değil.", 409
                )
        from .audit import record

        record(
            store, "directory_change_rejected", actor_id=actor.id, change_id=change_id
        )
        return {"status": "rejected"}

    @app.get("/api/v1/admin/security-events")
    def security_events(limit: int = 50):
        require_hr()
        with store.cs() as s:
            return [
                asdict(item)
                for item in s.scalars(
                    select(SecurityEvent)
                    .order_by(SecurityEvent.created_at.desc())
                    .limit(max(1, min(limit, 200)))
                )
            ]

    @app.post("/api/v1/admin/directory/test")
    def test_directory():
        try:
            app.state.auth.client_factory(directory_config(store, secret=True)).test()
            return {
                "status": "success",
                "message": "TLS, servis hesabı ve Base DN doğrulandı.",
            }
        except DomainError:
            raise
        except Exception:
            raise DomainError(
                "directory_test_failed",
                "AD bağlantısı doğrulanamadı. Sunucu, sertifika ve servis hesabını kontrol edin.",
                503,
            )

    @app.post("/api/v1/admin/directory/sync")
    def sync_directory():
        from .throttle import reserve

        reserve(store, "directory-sync", "all-admins", 2, 60)
        return app.state.auth.refresh_directory(force=True)

    @app.get("/api/v1/me/profile")
    def own_profile():
        actor = require_business()
        with store.session() as s:
            person = (
                get(s, Participant, actor.participant_id)
                if actor.participant_id
                else None
            )
            return {
                "identity": actor.public(),
                "participant": asdict(person) if person else None,
                "team": asdict(get(s, Team, person.team_id)) if person else None,
            }

    @app.get("/api/v1/me/results")
    def own_results():
        actor = require_business()
        if not actor.participant_id:
            return []
        with store.session() as s:
            result = []
            for pub in s.scalars(
                select(Publication).order_by(Publication.published_at.desc()).limit(50)
            ):
                snapshot = filter_snapshot(
                    s, pub.snapshot, actor, {actor.participant_id}
                )
                if snapshot["rows"]:
                    result.append(
                        {
                            "publication_id": pub.id,
                            "campaign_name": snapshot["campaign_name"],
                            "published_at": pub.published_at,
                            "source": "simulation" if snapshot["mock"] else "llm",
                            "version": pub.version,
                            "rows": snapshot["rows"],
                        }
                    )
            return result

    @app.get("/api/v1/development-actions")
    def actions():
        actor = require_business()
        with store.session() as s:
            return [
                asdict(x)
                for x in s.scalars(
                    select(DevelopmentAction).order_by(
                        DevelopmentAction.created_at.desc()
                    )
                )
                if action_visible(s, x, actor)
            ]

    def save_action(p, aid=None):
        actor = require_manager()
        if p.status not in ["planned", "in_progress", "completed", "archived"]:
            raise DomainError("invalid_status", "Gelişim planı durumu geçersiz.")
        with store.session() as s:
            if p.participant_id:
                person = get(s, Participant, p.participant_id)
                if not actor.sees(person.id):
                    raise DomainError("not_found", "Katılımcı bulunamadı.", 404)
                if p.team_id and p.team_id != person.team_id:
                    raise DomainError("invalid_scope", "Katılımcı bu ekibe ait değil.")
                p.team_id = person.team_id
            elif p.team_id:
                check_team(s, p.team_id, write=True)
            elif not actor.hr:
                raise DomainError(
                    "missing_scope",
                    "Plan için kendi ekibinizden bir katılımcı veya yönetebildiğiniz ekip seçin.",
                )
            if p.skill_id:
                get(s, Skill, p.skill_id)
            if p.publication_id:
                publication = get(s, Publication, p.publication_id)
                from .access import check_campaign

                check_campaign(s, publication.campaign_id)
            item = (
                get(s, DevelopmentAction, aid)
                if aid
                else DevelopmentAction(creator_id=actor.id)
            )
            if aid and not action_visible(s, item, actor):
                raise DomainError("not_found", "Gelişim planı bulunamadı.", 404)
            if aid and item.row_version != p.row_version:
                raise DomainError(
                    "revision_conflict",
                    "Plan başka bir kullanıcı tarafından değiştirildi. Yenileyin.",
                    409,
                )
            data = p.model_dump(exclude={"row_version"})
            data["due_date"] = p.due_date.isoformat() if p.due_date else None
            data["updated_at"] = now()
            if aid:
                changed = s.execute(
                    update(DevelopmentAction)
                    .where(
                        DevelopmentAction.id == aid,
                        DevelopmentAction.row_version == p.row_version,
                    )
                    .values(**data, row_version=p.row_version + 1)
                )
                if changed.rowcount != 1:
                    raise DomainError(
                        "revision_conflict",
                        "Plan başka bir kullanıcı tarafından değiştirildi. Yenileyin.",
                        409,
                    )
                s.refresh(item)
            else:
                for key, value in data.items():
                    setattr(item, key, value)
                s.add(item)
            s.flush()
            s.add(
                Audit(
                    action="development_action_saved",
                    entity_id=item.id,
                    detail={"actor_id": actor.id, "status": item.status},
                )
            )
            return asdict(item)

    @app.post("/api/v1/development-actions")
    def add_action(p: ActionInput):
        return save_action(p)

    @app.patch("/api/v1/development-actions/{aid}")
    def edit_action(aid: str, p: ActionInput):
        return save_action(p, aid)

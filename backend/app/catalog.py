"""HR-owned catalog changes preserve the competency content used by existing periods."""

from typing import Annotated
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from .models import Skill, Campaign, Question, Audit
from .store import DomainError, get
from .access import require_hr, require_business


def active_skill():
    return func.coalesce(Skill.metadata_["archived"].as_boolean(), False).is_(False)


def archived(skill):
    return bool(skill.metadata_.get("archived", False))


def skill_data(skill):
    from .services import COMMON

    meta = skill.metadata_
    return {
        "id": skill.id,
        "code": skill.code,
        "name": skill.name,
        "definition": skill.definition,
        "levels": skill.levels,
        "version": meta.get("catalog_version", 1),
        "archived": archived(skill),
        "common": skill.id in COMMON,
        **{
            key: meta.get(key, [] if key == "owners" else "")
            for key in ("owners", "domain", "family", "owner_department")
        },
    }


def skill_snapshot(skill):
    return {
        key: value
        for key, value in skill_data(skill).items()
        if key in {"id", "code", "name", "definition", "levels", "version"}
    }


def required_skills(config):
    from .services import COMMON

    common = config.get("common_skills", COMMON)
    ids = set(common)
    profiles = config.get("role_snapshots") or config.get("team_snapshots", {})
    for profile in profiles.values():
        ids.update(
            [
                t["skill_id"]
                for t in profile.get("targets", [])
                if t.get("applicable", True) and t["skill_id"] not in common
            ][:3]
        )
    return ids


def freeze_skills(s, config, allow_archived=False):
    ids = required_skills(config)
    rows = list(s.scalars(select(Skill).where(Skill.id.in_(list(ids)))))
    if not allow_archived and (
        len(rows) != len(ids) or any(archived(row) for row in rows)
    ):
        raise DomainError(
            "inactive_skill_target",
            "Seçili ekip/rol hedeflerinde silinmiş veya eksik yetkinlik var. Hedefleri güncelleyin ya da yetkinliği geri yükleyin.",
            409,
        )
    return {row.id: skill_snapshot(row) for row in rows}


def freeze_legacy_periods(s):
    # Called before editing catalog content. Lock periods in a stable order so two
    # HR edits cannot overwrite each other's one-time historical snapshot.
    periods = list(
        s.scalars(
            select(Campaign)
            .where(Campaign.config["skill_snapshots"].as_string().is_(None))
            .order_by(Campaign.id)
            .with_for_update()
        )
    )
    for period in periods:
        if not period.config.get("skill_snapshots"):
            config = dict(period.config)
            snapshots = freeze_skills(s, config, allow_archived=True)
            # Include any legacy form-specific skill that wasn't in its role targets.
            for skill in s.scalars(
                select(Skill).where(
                    Skill.id.in_(
                        select(Question.skill_id).where(
                            Question.campaign_id == period.id
                        )
                    )
                )
            ):
                snapshots.setdefault(skill.id, skill_snapshot(skill))
            period.config = {**config, "skill_snapshots": snapshots}


class LevelInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    level: int = Field(ge=1, le=5)
    label: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=2000)


class SkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: int = Field(ge=1, le=9999)
    name: str = Field(min_length=2, max_length=200)
    definition: str = Field(min_length=10, max_length=4000)
    levels: list[LevelInput] = Field(min_length=5, max_length=5)
    owners: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=20
    )
    domain: str = Field(default="", max_length=200)
    family: str = Field(default="", max_length=200)
    owner_department: str = Field(default="", max_length=200)
    expected_version: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def complete_levels(self):
        if {row.level for row in self.levels} != {1, 2, 3, 4, 5}:
            raise ValueError("L1–L5 tanımları birer kez girilmeli.")
        if (
            len(self.name.strip()) < 2
            or len(self.definition.strip()) < 10
            or any(
                not row.label.strip() or not row.description.strip()
                for row in self.levels
            )
            or any(not owner.strip() for owner in self.owners)
        ):
            raise ValueError("Ad, tanım ve seviye alanları boş olamaz.")
        return self


def install_catalog_routes(app, store):
    @app.get("/api/v1/catalog/skills")
    def listing(
        q: str = Query(default="", max_length=200),
        status: str = Query(default="active", pattern="^(active|archived|all)$"),
        offset: int = Query(default=0, ge=0, le=10000),
        limit: int = Query(default=24, ge=1, le=100),
    ):
        require_business()
        with store.session() as s:
            rows = list(s.scalars(select(Skill).order_by(Skill.code)))
            needle = q.strip().casefold()
            filtered = [
                row
                for row in rows
                if (status == "all" or archived(row) == (status == "archived"))
                and (
                    not needle
                    or needle
                    in (
                        str(row.code) + " " + row.name + " " + row.definition
                    ).casefold()
                )
            ]
            return {
                "items": [skill_data(row) for row in filtered[offset : offset + limit]],
                "total": len(filtered),
                "active_count": sum(not archived(row) for row in rows),
                "archived_count": sum(archived(row) for row in rows),
                "next_code": max((row.code for row in rows), default=0) + 1,
                "offset": offset,
                "limit": limit,
            }

    def mutation_quota(actor):
        from .throttle import reserve

        reserve(store, "catalog-write", actor.id, 60, 60)

    def fields(value):
        return {
            "name": value.name.strip(),
            "definition": value.definition.strip(),
            "levels": [
                {
                    "level": l.level,
                    "label": l.label.strip(),
                    "description": l.description.strip(),
                }
                for l in sorted(value.levels, key=lambda l: l.level)
            ],
        }

    def metadata(value):
        return {
            "owners": list(dict.fromkeys(owner.strip() for owner in value.owners)),
            "domain": value.domain.strip(),
            "family": value.family.strip(),
            "owner_department": value.owner_department.strip(),
        }

    def locked(s, sid, version):
        row = get(s, Skill, sid)
        changed = s.execute(
            update(Skill)
            .where(
                Skill.id == sid,
                func.coalesce(Skill.metadata_["catalog_version"].as_integer(), 1)
                == version,
            )
            .values({Skill.metadata_: Skill.metadata_})
        )
        if changed.rowcount != 1:
            raise DomainError(
                "catalog_conflict",
                "Yetkinlik başka bir işlemde değiştirildi. Güncel kaydı yükleyin.",
                409,
            )
        s.refresh(row)
        return row

    @app.post("/api/v1/skills", status_code=201)
    def create(value: SkillInput):
        actor = require_hr()
        mutation_quota(actor)
        try:
            with store.session() as s:
                row = Skill(
                    id=f"SKILL-{value.code:03d}",
                    code=value.code,
                    **fields(value),
                    metadata_={
                        **metadata(value),
                        "catalog_version": 1,
                        "archived": False,
                    },
                )
                s.add(row)
                s.flush()
                result = skill_data(row)
                s.add(
                    Audit(
                        action="catalog_skill_created",
                        entity_id=row.id,
                        detail={"actor_id": actor.id, "after": result},
                    )
                )
                return result
        except IntegrityError:
            raise DomainError(
                "skill_code_conflict",
                "Bu yetkinlik kodu kullanılıyor. Farklı bir kod seçin veya arşivdeki kaydı geri yükleyin.",
                409,
            )

    @app.patch("/api/v1/skills/{sid}")
    def edit(sid: str, value: SkillInput):
        actor = require_hr()
        mutation_quota(actor)
        with store.session() as s:
            row = locked(s, sid, value.expected_version)
            if archived(row):
                raise DomainError(
                    "skill_archived",
                    "Düzenlemek için önce yetkinliği geri yükleyin.",
                    409,
                )
            if value.code != row.code:
                raise DomainError(
                    "skill_code_immutable",
                    "Yetkinlik kodu oluşturulduktan sonra değiştirilemez.",
                    409,
                )
            before = skill_data(row)
            freeze_legacy_periods(s)
            for key, val in fields(value).items():
                setattr(row, key, val)
            row.metadata_ = {
                **row.metadata_,
                **metadata(value),
                "catalog_version": value.expected_version + 1,
            }
            s.add(
                Audit(
                    action="catalog_skill_updated",
                    entity_id=row.id,
                    detail={
                        "actor_id": actor.id,
                        "before": before,
                        "after": skill_data(row),
                    },
                )
            )
            return skill_data(row)

    @app.delete("/api/v1/skills/{sid}")
    def remove(sid: str, expected_version: int = Query(ge=1)):
        actor = require_hr()
        mutation_quota(actor)
        from .services import COMMON

        with store.session() as s:
            row = locked(s, sid, expected_version)
            if sid in COMMON:
                raise DomainError(
                    "common_skill_required",
                    "Bu yetkinlik zorunlu ortak ölçüm setinde kullanılıyor ve silinemez.",
                    409,
                )
            if archived(row):
                raise DomainError("skill_archived", "Yetkinlik zaten arşivde.", 409)
            before = skill_data(row)
            freeze_legacy_periods(s)
            row.metadata_ = {
                **row.metadata_,
                "archived": True,
                "catalog_version": expected_version + 1,
            }
            s.add(
                Audit(
                    action="catalog_skill_archived",
                    entity_id=row.id,
                    detail={
                        "actor_id": actor.id,
                        "before": before,
                        "after": skill_data(row),
                    },
                )
            )
            return skill_data(row)

    @app.post("/api/v1/skills/{sid}/restore")
    def restore(sid: str, expected_version: int = Query(ge=1)):
        actor = require_hr()
        mutation_quota(actor)
        with store.session() as s:
            row = locked(s, sid, expected_version)
            if not archived(row):
                raise DomainError("skill_active", "Yetkinlik zaten aktif.", 409)
            row.metadata_ = {
                **row.metadata_,
                "archived": False,
                "catalog_version": expected_version + 1,
            }
            s.add(
                Audit(
                    action="catalog_skill_restored",
                    entity_id=row.id,
                    detail={"actor_id": actor.id, "version": expected_version + 1},
                )
            )
            return skill_data(row)

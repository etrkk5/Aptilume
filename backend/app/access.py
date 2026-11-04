"""Authorization is derived from the server session and AD reporting graph."""

from sqlalchemy import select
from .models import *
from .security import current_actor, actor_for_user
from .store import DomainError, get


def require_business(actor=None):
    actor = actor or current_actor()
    if not actor.business:
        raise DomainError("forbidden", "Bu işlem için yetkiniz yok.", 403)
    return actor


def require_manager(actor=None):
    actor = actor or current_actor()
    if not actor.manager:
        raise DomainError(
            "forbidden", "Bu işlem için yönetici veya İK yetkisi gerekli.", 403
        )
    return actor


def require_hr():
    actor = current_actor()
    if not actor.hr:
        raise DomainError("forbidden", "Bu işlem için İK yetkisi gerekli.", 403)
    return actor


def require_integrations():
    actor = current_actor()
    if not actor.integrations:
        raise DomainError("forbidden", "Entegrasyon yönetimi yetkisi gerekli.", 403)
    return actor


def visible_team_ids(s, actor=None):
    actor = actor or current_actor()
    if actor.hr:
        return {t for t in s.scalars(select(Team.id))}
    return {
        t
        for t in s.scalars(
            select(Participant.team_id).where(
                Participant.id.in_(list(actor.participant_ids or []))
            )
        )
    }


def team_control(s, tid, actor=None):
    actor = actor or current_actor()
    if actor.hr:
        return True
    if not actor.manager:
        return False
    members = set(s.scalars(select(Participant.id).where(Participant.team_id == tid)))
    return bool(members) and members.issubset(actor.participant_ids or ())


def check_team(s, tid, write=False):
    actor = require_manager() if write else require_business()
    if write:
        if not team_control(s, tid, actor):
            raise DomainError(
                "forbidden", "Bu ekibin tamamını yönetme yetkiniz yok.", 403
            )
    elif tid not in visible_team_ids(s, actor):
        raise DomainError("not_found", "Ekip bulunamadı.", 404)


def campaign_people(s, campaign):
    existing = set(
        s.scalars(
            select(Assignment.participant_id).where(
                Assignment.campaign_id == campaign.id
            )
        )
    )
    if existing:
        return existing
    if "participant_ids" in campaign.config:
        return set(campaign.config["participant_ids"])
    return set(
        s.scalars(
            select(Participant.id).where(
                Participant.team_id.in_(list(campaign.config.get("team_snapshots", {})))
            )
        )
    )


def campaign_control(s, campaign, actor=None):
    actor = actor or current_actor()
    if actor.hr:
        return True
    people = campaign_people(s, campaign)
    return (
        actor.manager and bool(people) and people.issubset(actor.participant_ids or ())
    )


def check_campaign(s, cid, write=False):
    actor = require_manager() if write else require_business()
    campaign = get(s, Campaign, cid)
    if write and not campaign_control(s, campaign, actor):
        raise DomainError("forbidden", "Bu dönemin tamamını yönetme yetkiniz yok.", 403)
    if (
        not write
        and not actor.hr
        and not campaign_people(s, campaign).intersection(actor.participant_ids or ())
    ):
        raise DomainError("not_found", "Ölçüm dönemi bulunamadı.", 404)
    return campaign


def check_assignment(s, aid, write=False):
    actor = require_business()
    assignment = get(s, Assignment, aid)
    if write:
        if assignment.participant_id != actor.participant_id:
            raise DomainError(
                "forbidden",
                "Yanıt yalnızca anketin sahibi tarafından kaydedilebilir.",
                403,
            )
    elif not actor.sees(assignment.participant_id):
        raise DomainError("not_found", "Atama bulunamadı.", 404)
    return assignment


def filter_snapshot(s, snapshot, actor=None, participant_ids=None):
    actor = actor or current_actor()
    allowed = participant_ids if participant_ids is not None else actor.participant_ids
    if allowed is None:
        return snapshot
    allowed = set(allowed)
    assignment_ids = set(
        s.scalars(
            select(Assignment.id).where(Assignment.participant_id.in_(list(allowed)))
        )
    )
    rows = [r for r in snapshot["rows"] if r["participant_id"] in allowed]
    answers = [a for a in snapshot["answers"] if a["participant_id"] in allowed]
    answer_ids = {a["answer_id"] for a in answers}
    return {
        **snapshot,
        "rows": rows,
        "assignments": [
            a for a in snapshot["assignments"] if a["id"] in assignment_ids
        ],
        "answers": answers,
        "rubric_scores": [
            r for r in snapshot["rubric_scores"] if r["answer_id"] in answer_ids
        ],
        "insights": {},
        "profile_version": None,
    }


def export_snapshot(store, s, export):
    snapshot = get(s, Publication, export.publication_id).snapshot
    scope = s.get(ExportScope, export.id)
    if not scope:
        return snapshot
    actor = actor_for_user(store, scope.creator_id)
    if not actor.business:
        raise DomainError("export_access_revoked", "Rapor erişimi kaldırıldı.", 403)
    initial = None if scope.participant_ids is None else set(scope.participant_ids)
    current = None if actor.hr else set(actor.participant_ids or ())
    allowed = (
        current
        if initial is None
        else initial if current is None else current.intersection(initial)
    )
    return filter_snapshot(s, snapshot, actor, allowed)


def check_export(s, export, actor=None):
    actor = actor or current_actor()
    if actor.hr:
        return
    scope = s.get(ExportScope, export.id)
    if (
        not actor.business
        or not scope
        or scope.creator_id != actor.id
        or scope.participant_ids is None
        or not set(scope.participant_ids).issubset(actor.participant_ids or ())
    ):
        raise DomainError("not_found", "Dosya bulunamadı.", 404)

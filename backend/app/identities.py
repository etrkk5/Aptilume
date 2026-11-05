"""Provider-independent local identities, scoped provisioning and reporting links."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update, delete, func, or_
from .models import DirectoryUser, Participant, AuthSession, Setting, ControlEvent, uid
from .security import strong_password, passwords, password_capacity
from .access import require_integrations
from .store import DomainError


class UserInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)
    display_name: str = Field(min_length=2, max_length=200)
    email: str = Field(default="", max_length=254)
    role: Literal["admin", "hr", "manager", "employee"]
    participant_id: str | None = Field(default=None, max_length=100)
    manager_id: str | None = Field(default=None, max_length=100)
    active: bool = True
    password: str = Field(default="", max_length=128)


class CreateUserInput(UserInput):
    username: str = Field(
        min_length=3, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.@-]*$"
    )


def public_user(user, by_dn):
    return {
        "id": user.id,
        "username": user.username.removeprefix("ad:"),
        "display_name": user.display_name,
        "email": user.email,
        "roles": user.roles,
        "active": user.active,
        "source": user.source,
        "participant_id": user.participant_id,
        "manager_id": by_dn.get(user.manager_dn),
    }


def authorize_target(actor, user=None, role=None):
    # An integration administrator must not gain business access by resetting
    # an HR/employee password or by assigning a business identity to another login.
    if not actor.hr and (
        role not in (None, "admin") or user is not None and set(user.roles) != {"admin"}
    ):
        raise DomainError(
            "forbidden", "İş hesabı ve yetki yönetimi için İK yetkisi gerekli.", 403
        )


def mutate_user(store, payload, user_id=None):
    actor = require_integrations()
    if store.settings.presentation_demo:
        raise DomainError("identity_read_only", "Sunum kimlik deposu salt okunur.", 409)
    authorize_target(actor, role=payload.role)
    display_name = payload.display_name.strip()
    if len(display_name) < 2:
        raise DomainError("invalid_name", "Ad en az iki karakter olmalı.")
    password_hash = None
    if payload.password:
        if not strong_password(payload.password):
            raise DomainError(
                "weak_password", "Parola 15–128 karakterli ve güçlü olmalı."
            )
        with password_capacity():
            password_hash = passwords.hash(payload.password)
    elif user_id is None:
        raise DomainError("password_required", "Yeni hesap için parola gerekli.")
    with store.cs() as session:
        changed = session.execute(
            update(Setting)
            .where(
                Setting.key == "identity_revision",
                Setting.value["version"].as_integer() == payload.expected_version,
            )
            .values(value={"version": payload.expected_version + 1})
        )
        if changed.rowcount != 1:
            raise DomainError(
                "identity_conflict",
                "Hesap listesi değişti. Yenileyip tekrar kaydedin.",
                409,
            )
        user = (
            session.get(DirectoryUser, user_id, with_for_update=True)
            if user_id
            else None
        )
        if user_id and (not user or user.source != "local"):
            raise DomainError(
                "identity_read_only",
                "Bu hesap bağlı sağlayıcı tarafından yönetilir.",
                403,
            )
        authorize_target(actor, user, payload.role)
        old = None
        if user:
            old = {
                "roles": user.roles,
                "active": user.active,
                "participant_id": user.participant_id,
                "manager_dn": user.manager_dn,
            }
            if user.id == actor.id and (
                not payload.active or user.roles != [payload.role]
            ):
                raise DomainError(
                    "self_lockout",
                    "Kendi hesabınızı kapatamaz veya rolünüzü değiştiremezsiniz.",
                    409,
                )
            if user.id == "local-admin" and (
                not payload.active or payload.role != "admin"
            ):
                raise DomainError(
                    "bootstrap_protected",
                    "İlk kurulum admin hesabı etkin ve admin rolünde kalmalı.",
                    409,
                )
        else:
            username = payload.username.casefold()
            if username in {"admin", "hr"} or session.scalar(
                select(DirectoryUser.id).where(
                    func.lower(DirectoryUser.username) == username
                )
            ):
                raise DomainError(
                    "username_exists", "Bu kullanıcı adı ayrılmış veya kullanımda.", 409
                )
            user = DirectoryUser(
                id="local:" + uid(),
                username=username,
                display_name=display_name,
                source="local",
                groups=[],
                roles=[payload.role],
            )
            user.dn = user.id
            session.add(user)
        if payload.role in {"manager", "employee"}:
            if not payload.participant_id:
                raise DomainError(
                    "profile_required",
                    "Çalışan/yönetici hesabını bir çalışan profiliyle eşleştirin.",
                )
        elif payload.participant_id or payload.manager_id:
            raise DomainError(
                "invalid_identity_link",
                "Admin ve İK hesaplarına çalışan/yönetici ilişkisi atanmaz.",
            )
        if payload.participant_id:
            with store.session() as app_session:
                if not app_session.get(Participant, payload.participant_id):
                    raise DomainError(
                        "profile_not_found", "Çalışan profili bulunamadı.", 404
                    )
            if payload.active and session.scalar(
                select(DirectoryUser.id).where(
                    DirectoryUser.participant_id == payload.participant_id,
                    DirectoryUser.id != user.id,
                    DirectoryUser.active == True,
                )
            ):
                raise DomainError(
                    "profile_in_use",
                    "Bu profil başka bir etkin giriş hesabıyla eşleşmiş.",
                    409,
                )
        manager_dn = ""
        if payload.manager_id:
            manager = session.get(DirectoryUser, payload.manager_id)
            if (
                not manager
                or manager.source != "local"
                or not manager.active
                or "manager" not in manager.roles
            ):
                raise DomainError(
                    "invalid_manager", "Etkin bir yerel yönetici hesabı seçin."
                )
            if manager.id == user.id:
                raise DomainError(
                    "manager_cycle", "Hesap kendi yöneticisi olamaz.", 409
                )
            manager_dn = manager.dn
            by_dn = {
                u.dn: u
                for u in session.scalars(
                    select(DirectoryUser).where(DirectoryUser.source == "local")
                )
                if u.dn
            }
            current, visited = manager, {user.id}
            while current:
                if current.id in visited:
                    raise DomainError(
                        "manager_cycle", "Yönetici ilişkisi döngü oluşturamaz.", 409
                    )
                visited.add(current.id)
                current = by_dn.get(current.manager_dn)
        if old:
            if (not payload.active or payload.role != "manager") and "manager" in old[
                "roles"
            ]:
                if session.scalar(
                    select(DirectoryUser.id).where(
                        DirectoryUser.active == True,
                        DirectoryUser.manager_dn == user.dn,
                        DirectoryUser.id != user.id,
                    )
                ):
                    raise DomainError(
                        "manager_has_reports",
                        "Önce raporlayan hesapları başka yöneticiye taşıyın.",
                        409,
                    )
            for role in {"hr", "admin"} & set(old["roles"]):
                if not payload.active or payload.role != role:
                    others = session.scalars(
                        select(DirectoryUser).where(
                            DirectoryUser.active == True,
                            DirectoryUser.id != user.id,
                            DirectoryUser.source == "local",
                        )
                    )
                    if not any(role in other.roles for other in others):
                        raise DomainError(
                            "last_privileged_user",
                            "Son etkin İK/admin hesabı kapatılamaz.",
                            409,
                        )
        user.display_name = display_name
        user.email = payload.email.strip()
        user.roles, user.active = [payload.role], payload.active
        user.participant_id, user.manager_dn = payload.participant_id, manager_dn
        if password_hash:
            user.password_hash, user.temporary_password = password_hash, False
            if user.id == "local-admin":
                policy = session.get(Setting, "local_password_policy")
                if policy:
                    policy.value = {"version": 2}
                else:
                    session.add(
                        Setting(key="local_password_policy", value={"version": 2})
                    )
        session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        session.add(
            ControlEvent(
                profile_id=user.id,
                action="local_identity_updated" if old else "local_identity_created",
                detail={
                    "actor_id": actor.id,
                    "before": old,
                    "after": {
                        "roles": user.roles,
                        "active": user.active,
                        "participant_id": user.participant_id,
                        "manager_dn": user.manager_dn,
                    },
                    "password_changed": bool(password_hash),
                },
            )
        )
        return {"id": user.id, "version": payload.expected_version + 1}


def install_identity_routes(app, store):
    @app.get("/api/v1/admin/users")
    def users(q: str = "", offset: int = 0, limit: int = 50):
        actor = require_integrations()
        q = q[:100].casefold()
        with store.cs() as session:
            query = select(DirectoryUser)
            if not actor.hr:
                query = query.where(
                    DirectoryUser.roles[0].as_string() == "admin",
                    DirectoryUser.roles[1].as_string().is_(None),
                )
            if q:
                query = query.where(
                    or_(
                        *[
                            func.lower(column).contains(q, autoescape=True)
                            for column in [
                                DirectoryUser.username,
                                DirectoryUser.display_name,
                                DirectoryUser.email,
                            ]
                        ]
                    )
                )
            version = session.get(Setting, "identity_revision")
            start, size = max(0, offset), max(1, min(100, limit))
            total = session.scalar(select(func.count()).select_from(query.subquery()))
            page = list(
                session.scalars(
                    query.order_by(DirectoryUser.username).offset(start).limit(size)
                )
            )
            by_dn = dict(
                session.execute(
                    select(DirectoryUser.dn, DirectoryUser.id).where(
                        DirectoryUser.dn.in_(
                            [u.manager_dn for u in page if u.manager_dn]
                        )
                    )
                ).all()
            )
            managers = (
                list(
                    session.scalars(
                        select(DirectoryUser)
                        .where(
                            DirectoryUser.source == "local",
                            DirectoryUser.active == True,
                            DirectoryUser.roles[0].as_string() == "manager",
                        )
                        .order_by(DirectoryUser.display_name)
                        .limit(200)
                    )
                )
                if actor.hr
                else []
            )
            return {
                "items": [public_user(u, by_dn) for u in page],
                "total": total,
                "version": version.value["version"] if version else 1,
                "local_management_enabled": not store.settings.presentation_demo,
                "allowed_roles": (
                    ["admin", "hr", "manager", "employee"] if actor.hr else ["admin"]
                ),
                "managers": [
                    {"id": u.id, "display_name": u.display_name} for u in managers
                ],
            }

    @app.post("/api/v1/admin/users", status_code=201)
    def create_user(payload: CreateUserInput):
        return mutate_user(store, payload)

    @app.put("/api/v1/admin/users/{user_id}")
    def edit_user(user_id: str, payload: UserInput):
        return mutate_user(store, payload, user_id)

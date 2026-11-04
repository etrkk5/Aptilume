import hashlib
import hmac
import os
import secrets
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select, delete
from .models import DirectoryUser, AuthSession, LoginAttempt, Setting, ControlEvent
from .store import DomainError
from .directory import DirectoryClient, directory_config, synchronize

COOKIE = "aptilume_session"
actor_context = ContextVar("actor", default=None)
_sync_lock = threading.Lock()
passwords = PasswordHasher()


@dataclass(frozen=True)
class Actor:
    id: str
    username: str
    display_name: str
    email: str
    roles: frozenset
    participant_id: str | None
    participant_ids: frozenset | None
    csrf_token: str = ""
    temporary_password: bool = False

    @property
    def hr(self):
        return "hr" in self.roles

    @property
    def integrations(self):
        return bool(self.roles & {"hr", "admin"})

    @property
    def manager(self):
        return bool(self.roles & {"hr", "manager"})

    @property
    def business(self):
        return bool(self.roles & {"hr", "manager", "employee"})

    def sees(self, pid):
        return self.hr or pid in (self.participant_ids or ())

    def public(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "email": self.email,
            "roles": sorted(self.roles),
            "participant_id": self.participant_id,
            "csrf_token": self.csrf_token,
            "temporary_password": self.temporary_password,
            "scope_revision": hashlib.sha256(
                repr(
                    (
                        sorted(self.roles),
                        self.participant_id,
                        (
                            sorted(self.participant_ids)
                            if self.participant_ids is not None
                            else None
                        ),
                    )
                ).encode()
            ).hexdigest()[:20],
            "permissions": {
                "integrations": self.integrations,
                "manage_business": self.manager,
                "business": self.business,
                "all_data": self.hr,
            },
        }


def actor_for_user(store, user_id, csrf=""):
    with store.cs() as s:
        user = s.get(DirectoryUser, user_id)
        if not user or not user.active:
            raise DomainError(
                "session_invalid", "Oturum geçerli değil. Yeniden giriş yapın.", 401
            )
        roles = frozenset(user.roles)
        allowed = set()
        if roles & {"hr", "manager", "employee"} and user.participant_id:
            allowed.add(user.participant_id)
        if "manager" in roles:
            users = list(
                s.scalars(select(DirectoryUser).where(DirectoryUser.active == True))
            )
            frontier = {user.dn}
            visited = set()
            descendants = directory_config(store).get("include_descendants", True)
            while frontier:
                current = frontier - visited
                if not current:
                    break
                visited.update(current)
                children = [
                    u
                    for u in users
                    if u.manager_dn and u.manager_dn in current and u.id != user.id
                ]
                allowed.update(u.participant_id for u in children if u.participant_id)
                frontier = {u.dn for u in children} if descendants else set()
        return Actor(
            user.id,
            user.username.removeprefix("ad:"),
            user.display_name,
            user.email,
            roles,
            user.participant_id,
            None if "hr" in roles else frozenset(allowed),
            csrf,
            user.temporary_password,
        )


class AuthService:
    def __init__(self, store, client_factory=DirectoryClient):
        self.store = store
        self.client_factory = client_factory
        with store.cs() as s:
            admin = s.get(DirectoryUser, "local-admin")
            if not admin:
                pwd = os.getenv(
                    "BOOTSTRAP_ADMIN_PASSWORD", "admin" if store.settings.demo else ""
                )
                if (
                    not pwd
                    or not store.settings.demo
                    and (pwd == "admin" or len(pwd) < 12)
                ):
                    raise RuntimeError(
                        "Üretimde güçlü BOOTSTRAP_ADMIN_PASSWORD gerekli."
                    )
                s.add(
                    DirectoryUser(
                        id="local-admin",
                        username="admin",
                        display_name="Entegrasyon yöneticisi",
                        roles=["admin"],
                        groups=[],
                        source="local",
                        password_hash=passwords.hash(pwd),
                        temporary_password=pwd == "admin",
                    )
                )
            elif not store.settings.demo and admin.active and admin.temporary_password:
                raise RuntimeError(
                    "Üretime geçmeden geçici admin parolasını değiştirin."
                )

    def login(self, username, password, client_ip):
        username = username.strip()
        if not username or not password or len(username) > 254 or len(password) > 1024:
            raise DomainError(
                "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
            )
        key = hashlib.sha256(
            (client_ip + ":" + username.casefold()).encode()
        ).hexdigest()
        stamp = time.time()
        with self.store.cs() as s:
            count = len(
                list(
                    s.scalars(
                        select(LoginAttempt.id).where(
                            LoginAttempt.key == key,
                            LoginAttempt.created_at > stamp - 900,
                        )
                    )
                )
            )
            if count >= 5:
                raise DomainError(
                    "login_limited",
                    "Çok sayıda başarısız deneme. 15 dakika sonra tekrar deneyin.",
                    429,
                )
        try:
            if username.casefold() == "admin":
                with self.store.cs() as s:
                    identity = s.get(DirectoryUser, "local-admin")
                try:
                    verified = identity.active and passwords.verify(
                        identity.password_hash, password
                    )
                except VerificationError:
                    verified = False
                if not verified:
                    raise DomainError(
                        "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
                    )
                user_id = identity.id
            else:
                cfg = directory_config(self.store, secret=True)
                if not cfg["enabled"]:
                    raise DomainError(
                        "directory_not_configured",
                        "Active Directory henüz yapılandırılmamış. Entegrasyon yöneticisine başvurun.",
                        503,
                    )
                verified = self.client_factory(cfg).authenticate(username, password)
                self.refresh_directory(force=True)
                user_id = verified["id"]
                with self.store.cs() as s:
                    identity = s.get(DirectoryUser, user_id)
                    if not identity or not identity.active:
                        raise DomainError(
                            "invalid_credentials",
                            "Kullanıcı adı veya parola hatalı.",
                            401,
                        )
        except DomainError as exc:
            if exc.status == 401:
                with self.store.cs() as s:
                    s.add(LoginAttempt(key=key, created_at=stamp))
            raise
        with self.store.cs() as s:
            s.execute(delete(LoginAttempt).where(LoginAttempt.key == key))
            s.add(ControlEvent(profile_id=user_id, action="login_succeeded", detail={}))
        return self.create_session(user_id)

    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        stamp = time.time()
        with self.store.cs() as s:
            s.execute(delete(AuthSession).where(AuthSession.expires_at < stamp))
            s.add(
                AuthSession(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user_id,
                    csrf_token=csrf,
                    expires_at=stamp + 28800,
                    last_seen=stamp,
                )
            )
        return token, actor_for_user(self.store, user_id, csrf)

    def refresh_directory(self, force=False):
        cfg = directory_config(self.store)
        with self.store.cs() as s:
            row = s.get(Setting, "directory_sync")
            last = row.value.get("last_sync", 0) if row else 0
        if force or time.time() - last > cfg["sync_ttl"]:
            with _sync_lock:
                with self.store.cs() as s:
                    row = s.get(Setting, "directory_sync")
                    last = row.value.get("last_sync", 0) if row else 0
                if force or time.time() - last > cfg["sync_ttl"]:
                    return synchronize(self.store, self.client_factory)
        return {"last_sync": last}

    def actor(self, token, touch=True):
        if not token:
            raise DomainError(
                "authentication_required", "Giriş yapmanız gerekiyor.", 401
            )
        hashed = hashlib.sha256(token.encode()).hexdigest()
        stamp = time.time()
        with self.store.cs() as s:
            session = s.get(AuthSession, hashed)
            if (
                not session
                or session.expires_at < stamp
                or session.last_seen < stamp - 1800
            ):
                if session:
                    s.delete(session)
                raise DomainError(
                    "session_expired", "Oturumunuz sona erdi. Yeniden giriş yapın.", 401
                )
            user = s.get(DirectoryUser, session.user_id)
            if not user or not user.active:
                raise DomainError("session_invalid", "Oturum geçerli değil.", 401)
            user_id, csrf, source = user.id, session.csrf_token, user.source
            if touch:
                session.last_seen = stamp
        if source == "ldap":
            self.refresh_directory()
        return actor_for_user(self.store, user_id, csrf)

    def logout(self, token):
        if token:
            with self.store.cs() as s:
                s.execute(
                    delete(AuthSession).where(
                        AuthSession.token_hash
                        == hashlib.sha256(token.encode()).hexdigest()
                    )
                )

    def change_password(self, actor, current, new):
        if actor.id != "local-admin":
            raise DomainError(
                "directory_password",
                "Kurumsal parolanız Active Directory üzerinden yönetilir.",
                403,
            )
        if len(new) < 12 or new.casefold() in {"admin", "password1234"}:
            raise DomainError("weak_password", "Yeni parola en az 12 karakter olmalı.")
        with self.store.cs() as s:
            user = s.get(DirectoryUser, actor.id)
            try:
                passwords.verify(user.password_hash, current)
            except VerificationError:
                raise DomainError("invalid_password", "Mevcut parola hatalı.", 403)
            user.password_hash = passwords.hash(new)
            user.temporary_password = False
            s.execute(delete(AuthSession).where(AuthSession.user_id == actor.id))
            s.add(
                ControlEvent(
                    profile_id=actor.id, action="local_password_changed", detail={}
                )
            )


def current_actor():
    actor = actor_context.get()
    if not actor:
        raise DomainError("authentication_required", "Giriş yapmanız gerekiyor.", 401)
    return actor


def check_csrf(actor, value):
    if not value or not hmac.compare_digest(actor.csrf_token, value):
        raise DomainError(
            "csrf_failed", "Oturum doğrulaması başarısız. Sayfayı yenileyin.", 403
        )


def install_auth(app, store, auth):
    from fastapi import Request, Response
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool
    from pydantic import BaseModel, Field

    class LoginInput(BaseModel):
        username: str = Field(min_length=1, max_length=254)
        password: str = Field(min_length=1, max_length=1024)

    class PasswordInput(BaseModel):
        current_password: str
        new_password: str = Field(min_length=12, max_length=1024)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        reset = None
        try:
            if request.url.path.startswith("/api/"):
                origin = request.headers.get("origin")
                public = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
                allowed = {str(request.base_url).rstrip("/")}
                if public:
                    allowed.add(public)
                if origin and origin not in allowed:
                    raise DomainError(
                        "origin_denied", "İstek kaynağı doğrulanamadı.", 403
                    )
                if request.url.path != "/api/v1/auth/login":
                    actor = await run_in_threadpool(
                        auth.actor,
                        request.cookies.get(COOKIE),
                        request.headers.get("x-background-request") != "1",
                    )
                    if request.method not in ["GET", "HEAD", "OPTIONS"]:
                        check_csrf(actor, request.headers.get("x-csrf-token"))
                    reset = actor_context.set(actor)
                    request.state.actor = actor
                    path = request.url.path
                    if path.startswith("/api/v1/admin/") and not actor.integrations:
                        raise DomainError(
                            "forbidden", "Entegrasyon yönetimi yetkisi gerekli.", 403
                        )
                    if (
                        path.startswith(
                            (
                                "/api/v1/evaluation-runs",
                                "/api/v1/reviews",
                                "/api/v1/role-profiles",
                            )
                        )
                        and not actor.manager
                    ):
                        raise DomainError(
                            "forbidden",
                            "Bu işlem için yönetici veya İK yetkisi gerekli.",
                            403,
                        )
                    if path == "/api/v1/jobs" and not actor.hr:
                        raise DomainError(
                            "forbidden", "Bu işlem için İK yetkisi gerekli.", 403
                        )
                    if (
                        path == "/api/v1/catalog/import"
                        or path.startswith("/api/v1/participants")
                        or path == "/api/v1/teams"
                        and request.method == "POST"
                    ) and not actor.hr:
                        raise DomainError(
                            "forbidden", "Bu işlem için İK yetkisi gerekli.", 403
                        )
                    if not actor.business and not path.startswith(
                        (
                            "/api/v1/admin/",
                            "/api/v1/auth/",
                            "/api/v1/settings/",
                            "/api/v1/bootstrap",
                        )
                    ):
                        raise DomainError(
                            "forbidden",
                            "Bu hesap yalnızca entegrasyon yönetimine erişebilir.",
                            403,
                        )
            response = await call_next(request)
        except DomainError as exc:
            response = JSONResponse(
                status_code=exc.status,
                content={"code": exc.code, "message": exc.message},
            )
        finally:
            if reset is not None:
                actor_context.reset(reset)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if not store.settings.demo:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.post("/api/v1/auth/login")
    def login(p: LoginInput, request: Request, response: Response):
        token, actor = auth.login(
            p.username, p.password, request.client.host if request.client else "unknown"
        )
        auth.logout(request.cookies.get(COOKIE))
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=not store.settings.demo,
            samesite="lax",
            max_age=28800,
            path="/",
        )
        return actor.public()

    @app.get("/api/v1/auth/me")
    def me():
        return current_actor().public()

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response):
        auth.logout(request.cookies.get(COOKIE))
        response.delete_cookie(
            COOKIE,
            path="/",
            secure=not store.settings.demo,
            httponly=True,
            samesite="lax",
        )
        return {"status": "signed_out"}

    @app.post("/api/v1/auth/password")
    def change(p: PasswordInput, response: Response):
        auth.change_password(current_actor(), p.current_password, p.new_password)
        response.delete_cookie(COOKIE, path="/")
        return {"status": "signed_out"}

import hashlib
import hmac
import os
import secrets
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select, delete, update
from .models import DirectoryUser, AuthSession, LoginAttempt, Setting, ControlEvent
from .store import DomainError
from .directory import DirectoryClient, directory_config, synchronize

COOKIE = "aptilume_session"
actor_context = ContextVar("actor", default=None)
_sync_lock = threading.Lock()
_login_slots = threading.BoundedSemaphore(4)
passwords = PasswordHasher()


@contextmanager
def password_capacity():
    if not _login_slots.acquire(blocking=False):
        raise DomainError("login_busy", "Parola doğrulama hizmeti meşgul.", 429)
    try:
        yield
    finally:
        _login_slots.release()


def strong_password(value):
    return (
        isinstance(value, str)
        and 15 <= len(value) <= 128
        and value == value.strip()
        and len(set(value.casefold())) >= 6
        and value.casefold()
        not in {"password1234567", "admin1234567890", "changeme1234567"}
        and "admin" not in value.casefold()
        and value.casefold() != "123456789012345"
    )


def cookie_name(settings):
    return COOKIE if settings.demo else "__Host-" + COOKIE


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
    authenticated_at: float = 0

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


def actor_for_user(store, user_id, csrf="", authenticated_at=0):
    with store.cs() as s:
        user = s.get(DirectoryUser, user_id)
        if not user or not user.active:
            raise DomainError(
                "session_invalid", "Oturum geçerli değil. Yeniden giriş yapın.", 401
            )
        if user.source == "demo" and not store.settings.presentation_demo:
            raise DomainError(
                "session_invalid", "Demo oturumu bu ortamda geçersiz.", 401
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
            authenticated_at,
        )


class AuthService:
    def __init__(self, store, client_factory=DirectoryClient):
        self.store = store
        self.client_factory = client_factory
        with store.cs() as s:
            if store.settings.presentation_demo:
                if not s.get(Setting, "presentation_demo"):
                    raise RuntimeError("Sunum verisi için önce bootstrap çalıştırın.")
                return
            if s.get(Setting, "presentation_demo") or s.scalar(
                select(DirectoryUser.id).where(DirectoryUser.source == "demo").limit(1)
            ):
                raise RuntimeError("Demo kimlik deposu bu ortamda kullanılamaz.")
            admin = s.get(DirectoryUser, "local-admin")
            if not admin:
                pwd = os.getenv(
                    "BOOTSTRAP_ADMIN_PASSWORD", "admin" if store.settings.demo else ""
                )
                if not pwd or not store.settings.demo and not strong_password(pwd):
                    raise RuntimeError(
                        "Üretimde en az 15 karakterli güçlü BOOTSTRAP_ADMIN_PASSWORD gerekli."
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
                if strong_password(pwd):
                    s.add(Setting(key="local_password_policy", value={"version": 2}))
            elif (
                not store.settings.demo
                and admin.active
                and (
                    admin.temporary_password
                    or not s.get(Setting, "local_password_policy")
                    or s.get(Setting, "local_password_policy").value.get("version") != 2
                )
            ):
                raise RuntimeError(
                    "Üretime geçmeden geçici admin parolasını değiştirin."
                )

    def login(self, username, password, client_ip):
        from .throttle import reserve, refund
        from .audit import record

        username = username.strip()
        if not username or not password or len(username) > 254 or len(password) > 1024:
            raise DomainError(
                "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
            )
        reserve(self.store, "login-global", "all", 300, 60)
        reserve(self.store, "login-ip", client_ip, 90, 60)
        account = reserve(self.store, "login-account", username.casefold(), 5, 900)
        if not _login_slots.acquire(blocking=False):
            refund(self.store, account)
            raise DomainError(
                "login_busy",
                "Giriş hizmeti meşgul. Kısa süre sonra tekrar deneyin.",
                429,
            )
        try:
            if self.store.settings.presentation_demo:
                from .demo import authenticate_demo

                user_id = authenticate_demo(self.store, username, password)
            elif username.casefold() == "admin":
                with self.store.cs() as session:
                    identity = session.get(DirectoryUser, "local-admin")
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
                # Login performs a fresh user bind, while the full reporting tree uses its bounded TTL.
                self.refresh_directory()
                user_id = verified["id"]
                with self.store.cs() as session:
                    identity = session.get(DirectoryUser, user_id)
                if not identity or not identity.active:
                    raise DomainError(
                        "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
                    )
            token, actor = self.create_session(user_id)
            refund(self.store, account)
            record(self.store, "login_succeeded", actor_id=user_id)
            return token, actor
        except DomainError as exc:
            if exc.status != 401:
                refund(self.store, account)
            record(
                self.store,
                "login_failed",
                "denied",
                account_hash=hashlib.sha256(username.casefold().encode()).hexdigest(),
                reason=exc.code,
            )
            raise
        finally:
            _login_slots.release()

    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        stamp = time.time()
        with self.store.cs() as s:
            locked = s.execute(
                update(DirectoryUser)
                .where(DirectoryUser.id == user_id, DirectoryUser.active == True)
                .values(active=DirectoryUser.active)
            )
            if locked.rowcount != 1:
                raise DomainError("session_invalid", "Oturum geçerli değil.", 401)
            s.execute(delete(AuthSession).where(AuthSession.expires_at < stamp))
            previous = list(
                s.scalars(
                    select(AuthSession)
                    .where(AuthSession.user_id == user_id)
                    .order_by(AuthSession.last_seen.desc())
                )
            )
            for old in previous[4:]:
                s.delete(old)
            s.add(
                AuthSession(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    user_id=user_id,
                    csrf_token=csrf,
                    expires_at=stamp + 28800,
                    last_seen=stamp,
                )
            )
        return token, actor_for_user(self.store, user_id, csrf, stamp)

    def refresh_directory(self, force=False):
        cfg = directory_config(self.store)
        with self.store.cs() as s:
            row = s.get(Setting, "directory_sync")
            last = row.value.get("last_sync", 0) if row else 0
        if force or time.time() - last > cfg["sync_ttl"]:
            if not _sync_lock.acquire(timeout=2):
                raise DomainError(
                    "directory_sync_busy",
                    "Dizin güncelleniyor. Kısa süre sonra tekrar deneyin.",
                    503,
                )
            try:
                with self.store.cs() as s:
                    row = s.get(Setting, "directory_sync")
                    last = row.value.get("last_sync", 0) if row else 0
                if force or time.time() - last > cfg["sync_ttl"]:
                    return synchronize(self.store, self.client_factory)
            finally:
                _sync_lock.release()
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
            authenticated_at = session.expires_at - 28800
            if touch and session.last_seen < stamp - 30:
                session.last_seen = stamp
        if source == "ldap":
            self.refresh_directory()
        return actor_for_user(self.store, user_id, csrf, authenticated_at)

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
        from .throttle import reserve, refund

        key = reserve(self.store, "password-change", actor.id, 5, 900)
        if not strong_password(new):
            raise DomainError(
                "weak_password",
                "Yeni parola 15–128 karakter olmalı; tekrarlı, yaygın veya kullanıcı adını içeren bir parola kullanmayın.",
            )
        with password_capacity():
            with self.store.cs() as s:
                user = s.get(DirectoryUser, actor.id)
                try:
                    passwords.verify(user.password_hash, current)
                except VerificationError:
                    raise DomainError("invalid_password", "Mevcut parola hatalı.", 403)
                user.password_hash = passwords.hash(new)
                user.temporary_password = False
                policy = s.get(Setting, "local_password_policy")
                if policy:
                    policy.value = {"version": 2}
                else:
                    s.add(Setting(key="local_password_policy", value={"version": 2}))
                s.execute(delete(AuthSession).where(AuthSession.user_id == actor.id))
                s.add(
                    ControlEvent(
                        profile_id=actor.id, action="local_password_changed", detail={}
                    )
                )
        refund(self.store, key)


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
        current_password: str = Field(max_length=1024)
        new_password: str = Field(min_length=15, max_length=128)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        reset = None
        try:
            if request.url.path.startswith("/api/"):
                name = cookie_name(store.settings)
                if (
                    sum(
                        part.strip().partition("=")[0] == name
                        for part in request.headers.get("cookie", "").split(";")
                    )
                    > 1
                ):
                    raise DomainError(
                        "ambiguous_cookie", "Oturum çerezi geçersiz.", 400
                    )
                if request.url.path != "/api/v1/auth/login":
                    actor = await run_in_threadpool(
                        auth.actor,
                        request.cookies.get(name),
                        request.headers.get("x-background-request") != "1",
                    )
                    if request.method not in ["GET", "HEAD", "OPTIONS"]:
                        check_csrf(actor, request.headers.get("x-csrf-token"))
                    reset = actor_context.set(actor)
                    request.state.actor = actor
                    path = request.url.path
                    critical = (
                        (path == "/api/v1/admin/directory" and request.method == "PUT")
                        or path.startswith("/api/v1/admin/service-bindings/")
                        or (
                            path.startswith("/api/v1/admin/directory/changes/")
                            and path.endswith("/approve")
                        )
                    )
                    if critical and time.time() - actor.authenticated_at > 900:
                        raise DomainError(
                            "reauthentication_required",
                            "Bu hassas işlem için yeniden giriş yapın.",
                            401,
                        )
                    from .throttle import reserve

                    reserve(
                        store,
                        (
                            "api-reads"
                            if request.method in ["GET", "HEAD"]
                            else "api-writes"
                        ),
                        actor.id,
                        600 if request.method in ["GET", "HEAD"] else 120,
                        60,
                    )
                    if request.method not in ["GET", "HEAD", "OPTIONS"]:
                        if path == "/api/v1/exports":
                            reserve(store, "exports", actor.id, 5, 600)
                            reserve(store, "exports-global", "all", 100, 600)
                        elif path == "/api/v1/campaigns":
                            reserve(store, "campaign-create", actor.id, 10, 3600)
                        elif path.endswith(
                            ("/evaluation-runs", "/retry-failed", "/generate-questions")
                        ):
                            reserve(store, "llm-jobs", actor.id, 10, 3600)
                        elif path.startswith("/api/v1/admin/"):
                            reserve(store, "admin-operations", actor.id, 60, 60)
                            if path.endswith(("/test", "/sync")):
                                reserve(store, "integration-tests", actor.id, 10, 60)
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
            if (
                request.url.path.startswith("/api/")
                and request.method not in ["GET", "HEAD", "OPTIONS"]
                and response.status_code < 400
            ):
                from .audit import record

                route = request.scope.get("route")
                record(
                    store,
                    "sensitive_operation",
                    actor_id=getattr(getattr(request.state, "actor", None), "id", ""),
                    kind=getattr(route, "path", "unknown"),
                    method=request.method,
                    status=response.status_code,
                    target_id=next(iter(request.path_params.values()), ""),
                )
        except DomainError as exc:
            from .audit import record

            record(
                store,
                "request_denied",
                "denied",
                actor_id=getattr(getattr(request.state, "actor", None), "id", ""),
                reason=exc.code,
                method=request.method,
                status=exc.status,
            )
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
        auth.logout(request.cookies.get(cookie_name(store.settings)))
        response.set_cookie(
            cookie_name(store.settings),
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
        auth.logout(request.cookies.get(cookie_name(store.settings)))
        response.delete_cookie(
            cookie_name(store.settings),
            path="/",
            secure=not store.settings.demo,
            httponly=True,
            samesite="lax",
        )
        return {"status": "signed_out"}

    @app.post("/api/v1/auth/password")
    def change(p: PasswordInput, response: Response):
        auth.change_password(current_actor(), p.current_password, p.new_password)
        response.delete_cookie(
            cookie_name(store.settings),
            path="/",
            secure=not store.settings.demo,
            httponly=True,
            samesite="lax",
        )
        return {"status": "signed_out"}

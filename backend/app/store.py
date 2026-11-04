import json
import os
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from .config import Settings
from .models import (
    Base,
    ControlBase,
    Profile,
    ProfileVersion,
    Binding,
    ControlEvent,
    Campaign,
    Run,
    Job,
    uid,
)


class DomainError(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status


def engine_for(url):
    sqlite = str(url).startswith("sqlite")
    engine = create_engine(
        url,
        connect_args=({"check_same_thread": False, "timeout": 30} if sqlite else {}),
        pool_pre_ping=True,
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def sqlite_config(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")

    return engine


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        os.umask(0o007)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        keyfile = settings.data_dir / ".encryption-key"
        if settings.secret_key:
            key = settings.secret_key.encode()
        elif settings.demo:
            try:
                fd = os.open(keyfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
            except FileExistsError:
                key = keyfile.read_bytes()
            else:
                key = Fernet.generate_key()
                with os.fdopen(fd, "wb") as f:
                    f.write(key)
        else:
            raise RuntimeError("SECRET_ENCRYPTION_KEY gerekli")
        self.cipher = Fernet(key)
        self.control = engine_for(settings.control_url)
        ControlBase.metadata.create_all(self.control)
        self.control_session = sessionmaker(self.control, expire_on_commit=False)
        self._engine, self._binding_version = None, None
        with self.cs() as s:
            if not s.get(Binding, "application_db"):
                cfg = {
                    "engine": "sqlite",
                    "path": str(settings.data_dir / "application.db"),
                }
                p = self._new_profile(s, "db", "Yerel geliştirme", cfg, None)
                s.add(Binding(purpose="application_db", version_id=f"{p.id}:1"))
            if not s.get(Binding, "evaluation"):
                p = self._new_profile(
                    s,
                    "llm",
                    "Mock · Development",
                    {
                        "provider": "mock",
                        "model": "apt-mock-v1",
                        "endpoint": "mock://apt-lab",
                        "timeout": 90,
                        "concurrency": 3,
                        "scenario": "success",
                    },
                    None,
                )
                for purpose in ["generation", "evaluation", "insights"]:
                    s.add(Binding(purpose=purpose, version_id=f"{p.id}:1"))
        self.application_error = None
        try:
            Base.metadata.create_all(self.engine)
        except Exception:
            # Configuration recovery must remain available when the application DB is down.
            self.application_error = "application_store_unavailable"

    @contextmanager
    def cs(self):
        with self.control_session.begin() as s:
            yield s

    @contextmanager
    def session(self):
        with sessionmaker(self.engine, expire_on_commit=False).begin() as s:
            yield s

    @property
    def engine(self):
        with self.cs() as s:
            binding = s.get(Binding, "application_db")
            version = s.get(ProfileVersion, binding.version_id)
            config, secret = version.config, version.secret
        if self._binding_version != binding.version_id:
            if self._engine:
                self._engine.dispose()
            self._engine = engine_for(self.db_url(config, self.decrypt(secret)))
            self._binding_version = binding.version_id
        return self._engine

    def db_url(self, c, secret=None):
        from sqlalchemy.engine import URL

        if c.get("engine") == "sqlite":
            path = Path(
                c.get("path", str(self.settings.data_dir / "application.db"))
            ).resolve()
            if not path.is_relative_to(self.settings.data_dir):
                raise DomainError(
                    "invalid_path", "SQLite dosyası DATA_DIR içinde olmalı."
                )
            return f"sqlite:///{path}"
        if c.get("engine") == "postgresql":
            query = {
                "sslmode": c.get("sslmode", "require"),
                "connect_timeout": str(c.get("timeout", 10)),
            }
            return URL.create(
                "postgresql+psycopg",
                username=c.get("username"),
                password=secret,
                host=c.get("host"),
                port=int(c.get("port", 5432)),
                database=c.get("database"),
                query=query,
            )
        raise DomainError("unsupported_engine", "Bu DB sürücüsü henüz desteklenmiyor.")

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode() if value else None

    def decrypt(self, value):
        return self.cipher.decrypt(value.encode()).decode() if value else None

    def _new_profile(self, s, kind, name, config, secret):
        p = Profile(
            id=uid(), kind=kind, name=name, config=config, secret=self.encrypt(secret)
        )
        s.add(p)
        s.flush()
        s.add(
            ProfileVersion(
                id=f"{p.id}:1",
                profile_id=p.id,
                version=1,
                config=config,
                secret=p.secret,
            )
        )
        return p

    def profiles(self, kind=None):
        with self.cs() as s:
            bindings = {b.purpose: b.version_id for b in s.scalars(select(Binding))}
            q = select(Profile).where(Profile.deleted == False)
            if kind:
                q = q.where(Profile.kind == kind)
            return [
                dict(
                    id=p.id,
                    kind=p.kind,
                    name=p.name,
                    version=p.version,
                    config=p.config,
                    has_secret=bool(p.secret),
                    active_for=[
                        k for k, v in bindings.items() if v == f"{p.id}:{p.version}"
                    ],
                    outdated_bindings=[
                        k
                        for k, v in bindings.items()
                        if v.startswith(p.id + ":") and v != f"{p.id}:{p.version}"
                    ],
                    created_at=p.created_at,
                )
                for p in s.scalars(q)
            ]

    def save_profile(
        self, kind, name, config, secret=None, profile_id=None, clear_secret=False
    ):
        if kind not in ["llm", "db"]:
            raise DomainError("invalid_kind", "Bağlantı türü geçersiz.")
        if kind == "db":
            self.db_url(config, secret)
        else:
            if config.get("provider") not in [
                "mock",
                "openai_responses",
                "openai_compatible_chat",
            ]:
                raise DomainError("invalid_provider", "LLM protokolü desteklenmiyor.")
            if not config.get("model"):
                raise DomainError("missing_model", "Model adı gerekli.")
            if not 1 <= int(config.get("concurrency", 3)) <= 20:
                raise DomainError("invalid_concurrency", "Paralellik 1–20 olmalı.")
        with self.cs() as s:
            if profile_id:
                p = s.get(Profile, profile_id)
                if not p or p.deleted or p.kind != kind:
                    raise DomainError("not_found", "Profil bulunamadı.", 404)
                # Binding versions stay pinned until the administrator explicitly activates the edit.
                p.version += 1
                p.name = name
                p.config = config
                if clear_secret:
                    p.secret = None
                elif secret:
                    p.secret = self.encrypt(secret)
                s.add(
                    ProfileVersion(
                        id=f"{p.id}:{p.version}",
                        profile_id=p.id,
                        version=p.version,
                        config=config,
                        secret=p.secret,
                    )
                )
            else:
                p = self._new_profile(s, kind, name, config, secret)
            s.add(
                ControlEvent(
                    profile_id=p.id,
                    action="profile_saved",
                    detail={"kind": kind, "version": p.version},
                )
            )
            result = p.id
        return next(p for p in self.profiles(kind) if p["id"] == result)

    def resolve(self, purpose=None, version_id=None):
        with self.cs() as s:
            if not version_id:
                version_id = s.get(Binding, purpose).version_id
            v = s.get(ProfileVersion, version_id)
            if not v:
                raise DomainError("missing_profile", "Bağlantı sürümü bulunamadı.")
            if not self.settings.demo and v.config.get("provider") == "mock":
                raise DomainError(
                    "production_llm_required",
                    "Üretimde gerçek bir LLM bağlantısını etkinleştirin.",
                    409,
                )
            return {**v.config, "secret": self.decrypt(v.secret), "version_id": v.id}

    def delete_profile(self, pid):
        with self.cs() as s:
            p = s.get(Profile, pid)
            if not p or p.deleted:
                raise DomainError("not_found", "Profil bulunamadı.", 404)
            if any(
                b.version_id.startswith(pid + ":") for b in s.scalars(select(Binding))
            ):
                raise DomainError(
                    "profile_in_use",
                    "Aktif profil için önce başka bağlantı seçin.",
                    409,
                )
            with self.session() as app:
                if any(
                    r.profile_version.startswith(pid + ":")
                    or r.insight_profile_version.startswith(pid + ":")
                    for r in app.scalars(
                        select(Run).where(
                            Run.status.in_(["queued", "evaluating", "validating"])
                        )
                    )
                ):
                    raise DomainError(
                        "profile_in_use",
                        "Çalışan değerlendirme bu profili kullanıyor.",
                        409,
                    )
            p.deleted = True
            # Retain version metadata for historical runs; purge secret material only for unused versions.
            s.add(ControlEvent(profile_id=pid, action="profile_deleted", detail={}))

    def bind(self, purpose, pid):
        if purpose not in ["generation", "evaluation", "insights", "application_db"]:
            raise DomainError("invalid_binding", "Görev tanımsız.")
        if purpose == "application_db":
            raise DomainError(
                "migration_required",
                "DB geçişi için migration önizleme ve aktivasyon akışını kullanın.",
                409,
            )
        with self.cs() as s:
            p = s.get(Profile, pid)
            if not p or p.deleted or p.kind != "llm":
                raise DomainError("not_found", "LLM profili bulunamadı.", 404)
            b = s.get(Binding, purpose)
            b.version_id = f"{p.id}:{p.version}"
            s.add(
                ControlEvent(
                    profile_id=pid,
                    action="binding_changed",
                    detail={"purpose": purpose, "version": p.version},
                )
            )

    def activate_db(self, pid, copy_existing=True):
        """Offline migration: validate and copy before changing the control-store binding."""
        from sqlalchemy import inspect, insert

        with self.session() as s:
            if s.scalar(
                select(Campaign.id).where(Campaign.status == "open")
            ) or s.scalar(select(Job.id).where(Job.status.in_(["queued", "running"]))):
                raise DomainError(
                    "maintenance_required",
                    "Açık kampanyaları ve çalışan işleri tamamlayın.",
                    409,
                )
        with self.cs() as s:
            p = s.get(Profile, pid)
            if not p or p.deleted or p.kind != "db":
                raise DomainError("not_found", "DB profili bulunamadı.", 404)
            cfg, secret, vid = p.config, self.decrypt(p.secret), f"{p.id}:{p.version}"
            if s.get(Binding, "application_db").version_id == vid:
                return {"status": "already_active"}
        target = engine_for(self.db_url(cfg, secret))
        identity = lambda url: (
            url.get_backend_name(),
            url.host,
            url.port,
            url.database,
        )
        if identity(target.url) == identity(self.engine.url):
            try:
                with target.connect() as c:
                    c.execute(text("SELECT 1"))
                with self.cs() as s:
                    s.get(Binding, "application_db").version_id = vid
                    s.add(
                        ControlEvent(
                            profile_id=pid, action="database_profile_rotated", detail={}
                        )
                    )
                self.engine
                return {"status": "activated", "counts": {}, "same_database": True}
            finally:
                target.dispose()
        Base.metadata.create_all(target)
        counts = {}
        try:
            with self.engine.connect() as src, target.begin() as dest:
                for table in Base.metadata.sorted_tables:
                    if dest.execute(select(table)).first():
                        raise DomainError(
                            "target_not_empty",
                            "Güvenli taşıma için hedef veritabanı boş olmalı.",
                            409,
                        )
                    rows = (
                        [dict(r) for r in src.execute(select(table)).mappings()]
                        if copy_existing
                        else []
                    )
                    if rows:
                        dest.execute(insert(table), rows)
                    written = [dict(r) for r in dest.execute(select(table)).mappings()]
                    canonical = lambda v: sorted(
                        json.dumps(r, sort_keys=True, default=str, ensure_ascii=False)
                        for r in v
                    )
                    if canonical(rows) != canonical(written):
                        raise DomainError(
                            "migration_mismatch", "Taşıma doğrulaması başarısız.", 500
                        )
                    counts[table.name] = len(rows)
            with self.cs() as s:
                s.get(Binding, "application_db").version_id = vid
                s.add(
                    ControlEvent(
                        profile_id=pid,
                        action="database_activated",
                        detail={"counts": counts},
                    )
                )
            self.engine
            return {"status": "activated", "counts": counts}
        finally:
            target.dispose()


def get(s, model, key):
    obj = s.get(model, key)
    if not obj:
        raise DomainError("not_found", "Kayıt bulunamadı.", 404)
    return obj

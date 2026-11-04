"""Active Directory authentication and identity synchronization over verified TLS."""

import re
import ssl
import time
from uuid import UUID
from ldap3 import (
    Server,
    Connection,
    Tls,
    SUBTREE,
    BASE,
    AUTO_BIND_NO_TLS,
    AUTO_BIND_TLS_BEFORE_BIND,
)
from ldap3.core.exceptions import LDAPException, LDAPBindError
from ldap3.utils.conv import escape_filter_chars
from sqlalchemy import select, update
from .models import (
    Setting,
    DirectoryUser,
    Participant,
    Team,
    uid,
    ControlEvent,
    DirectoryChange,
)
from .store import DomainError

DEFAULT_DIRECTORY = {
    "enabled": False,
    "host": "",
    "port": 636,
    "transport": "ldaps",
    "base_dn": "",
    "bind_dn": "",
    "username_attribute": "sAMAccountName",
    "guid_attribute": "objectGUID",
    "manager_attribute": "manager",
    "department_attribute": "department",
    "title_attribute": "title",
    "display_attribute": "displayName",
    "email_attribute": "mail",
    "ca_file": "",
    "nested_groups": True,
    "include_descendants": True,
    "sync_ttl": 300,
    "role_groups": {"hr": [], "admin": [], "manager": []},
    "department_map": {},
}


def directory_config(store, secret=False):
    with store.cs() as s:
        row = s.get(Setting, "directory")
        config = {**DEFAULT_DIRECTORY, **(row.value if row else {})}
    encrypted = config.pop("encrypted_password", None)
    config["has_secret"] = bool(encrypted)
    if secret:
        config["password"] = store.decrypt(encrypted)
        config["_network_policy"] = {
            "production": not store.settings.demo,
            "allowed": store.settings.allowed_directory_hosts,
            "cidrs": store.settings.allowed_cidrs,
        }
    return config


def _prepare_directory_config(store, data, base=None):
    current = base or directory_config(store, secret=True)
    if not isinstance(data, dict) or any(len(str(v)) > 65536 for v in data.values()):
        raise DomainError("invalid_directory", "Dizin yapılandırması geçersiz.")
    if "encrypted_password" in data and not isinstance(data.get("password"), str):
        raise DomainError("invalid_directory", "Şifreli alan doğrudan değiştirilemez.")
    config = {k: v for k, v in data.items() if k in DEFAULT_DIRECTORY}
    config = {**{k: v for k, v in current.items() if k in DEFAULT_DIRECTORY}, **config}
    for key, default in DEFAULT_DIRECTORY.items():
        value = config[key]
        if isinstance(default, bool) and not isinstance(value, bool):
            raise DomainError("invalid_directory", "Dizin seçenekleri geçersiz.")
        if isinstance(default, str) and not isinstance(value, str):
            raise DomainError("invalid_directory", "Dizin alanları metin olmalı.")
        if isinstance(value, str):
            config[key] = value.strip()
            if len(config[key]) > (4096 if key == "ca_file" else 2048):
                raise DomainError("invalid_directory", "Dizin alanı çok uzun.")
    if any(
        not isinstance(config[k], int) or isinstance(config[k], bool)
        for k in ["port", "sync_ttl"]
    ):
        raise DomainError("invalid_directory", "Port ve yenileme süresi sayı olmalı.")
    if not isinstance(config["role_groups"], dict) or not isinstance(
        config["department_map"], dict
    ):
        raise DomainError("invalid_directory", "Grup ve departman eşlemeleri geçersiz.")
    if any(
        not isinstance(k, str) or not isinstance(v, str) or not v.strip()
        for k, v in config["department_map"].items()
    ):
        raise DomainError("invalid_directory", "Departman eşlemeleri metin olmalı.")
    if config["transport"] not in ["ldaps", "starttls"]:
        raise DomainError(
            "invalid_directory", "LDAP bağlantısı LDAPS veya StartTLS kullanmalı."
        )
    if not 1 <= int(config["port"]) <= 65535 or not 60 <= int(config["sync_ttl"]) <= (
        3600 if store.settings.demo else 300
    ):
        raise DomainError("invalid_directory", "Port veya yenileme süresi geçersiz.")
    for key in [k for k in config if k.endswith("_attribute")]:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", config[key]):
            raise DomainError("invalid_directory", "LDAP alan adları geçersiz.")
    if set(config["role_groups"]) - {"hr", "admin", "manager", "employee"}:
        raise DomainError("invalid_directory", "Rol eşlemesi geçersiz.")
    if any(
        not isinstance(v, list) or any(not isinstance(x, str) for x in v)
        for v in config["role_groups"].values()
    ):
        raise DomainError("invalid_directory", "Grup DN değerleri liste olmalı.")
    if (
        any(
            len(groups) > 20 or any(len(group) > 2048 for group in groups)
            for groups in config["role_groups"].values()
        )
        or len(config["department_map"]) > 1000
    ):
        raise DomainError(
            "invalid_directory", "Grup veya departman eşleme sınırı aşıldı."
        )
    config["role_groups"] = {
        role: [group.strip() for group in groups if group.strip()]
        for role, groups in config["role_groups"].items()
    }
    password = (
        ""
        if data.get("clear_secret")
        else data.get("password") or current.get("password")
    )
    if password is not None and (not isinstance(password, str) or len(password) > 4096):
        raise DomainError("invalid_directory", "Servis parolası geçersiz.")
    if (
        current.get("has_secret")
        and any(config[k] != current.get(k) for k in ["host", "port", "bind_dn"])
        and not data.get("password")
    ):
        raise DomainError(
            "directory_secret_required",
            "Sunucu veya servis hesabı değiştiği için parolayı tekrar girin.",
        )
    if config["enabled"] and (
        not config["host"]
        or not config["base_dn"]
        or not config["bind_dn"]
        or not password
    ):
        raise DomainError(
            "incomplete_directory",
            "Etkinleştirmek için sunucu, Base DN, servis hesabı ve parola gerekli.",
        )
    if config["host"] and (
        "://" in config["host"] or "/" in config["host"] or "@" in config["host"]
    ):
        raise DomainError(
            "invalid_directory", "Sunucu alanına yalnızca host adını yazın."
        )
    if not store.settings.demo and config["host"]:
        from .network import hostname, permitted_host

        hostname(config["host"])
        permitted_host(
            config["host"], config["port"], store.settings.allowed_directory_hosts
        )
        if config["enabled"] and not config["role_groups"].get("hr"):
            raise DomainError(
                "missing_hr_group", "Üretimde en az bir İK grubu DN tanımlanmalı."
            )
    config["encrypted_password"] = store.encrypt(password)
    return config


def _apply_directory_config(s, config):
    row = s.get(Setting, "directory")
    if row:
        row.value = config
    else:
        s.add(Setting(key="directory", value=config))
    state = s.get(Setting, "directory_sync")
    if state:
        state.value = {"last_sync": 0}
    from sqlalchemy import delete
    from .models import AuthSession

    ldap_users = list(
        s.scalars(select(DirectoryUser.id).where(DirectoryUser.source == "ldap"))
    )
    if ldap_users:
        s.execute(delete(AuthSession).where(AuthSession.user_id.in_(ldap_users)))
    s.add(
        ControlEvent(
            profile_id="directory",
            action="directory_configured",
            detail={"enabled": config["enabled"]},
        )
    )


def save_directory_config(store, data):
    config = _prepare_directory_config(store, data)
    with store.cs() as s:
        _apply_directory_config(s, config)
    return directory_config(store)


def directory_protected(store):
    with store.cs() as s:
        return bool(
            s.get(Setting, "directory_initialized")
            or s.scalar(
                select(DirectoryUser.id).where(DirectoryUser.source == "ldap").limit(1)
            )
        )


def public_change(change):
    config = {
        key: value
        for key, value in change.config.items()
        if key != "encrypted_password"
    }
    return {
        "id": change.id,
        "config": {
            **config,
            "has_secret": bool(change.config.get("encrypted_password")),
        },
        "requested_by": change.requested_by,
        "created_at": change.created_at,
        "status": change.status,
    }


def propose_directory_change(store, data, actor):
    from .audit import record

    if actor.hr or not directory_protected(store):
        config = _prepare_directory_config(store, data)
        with store.cs() as s:
            _apply_directory_config(s, config)
            s.execute(
                update(DirectoryChange)
                .where(DirectoryChange.status == "pending")
                .values(status="superseded")
            )
        record(store, "directory_policy_applied", actor_id=actor.id)
        return {**directory_config(store), "status": "applied"}
    base = None
    with store.cs() as s:
        previous = s.scalar(
            select(DirectoryChange)
            .where(
                DirectoryChange.status == "pending",
                DirectoryChange.requested_by == actor.id,
            )
            .order_by(DirectoryChange.created_at.desc())
            .limit(1)
        )
        if previous:
            base = {
                **previous.config,
                "password": store.decrypt(previous.config.get("encrypted_password")),
                "has_secret": bool(previous.config.get("encrypted_password")),
            }
    config = _prepare_directory_config(store, data, base)
    with store.cs() as s:
        s.execute(
            update(DirectoryChange)
            .where(DirectoryChange.status == "pending")
            .values(status="superseded")
        )
        change = DirectoryChange(config=config, requested_by=actor.id)
        s.add(change)
        s.flush()
        result = public_change(change)
    record(
        store, "directory_change_proposed", actor_id=actor.id, change_id=result["id"]
    )
    return {"status": "pending_approval", "change": result}


def approve_directory_change(store, change_id, actor):
    if not actor.hr:
        raise DomainError(
            "forbidden", "AD güven politikasını uygulamak için İK yetkisi gerekli.", 403
        )
    with store.cs() as s:
        change = s.get(DirectoryChange, change_id)
        if not change or change.status != "pending":
            raise DomainError(
                "change_conflict", "Değişiklik bekleyen durumda değil.", 409
            )
        data = {
            **{k: v for k, v in change.config.items() if k != "encrypted_password"},
            "password": store.decrypt(change.config.get("encrypted_password")),
        }
    config = _prepare_directory_config(store, data)
    with store.cs() as s:
        changed = s.execute(
            update(DirectoryChange)
            .where(DirectoryChange.id == change_id, DirectoryChange.status == "pending")
            .values(status="approved", approved_by=actor.id)
        )
        if changed.rowcount != 1:
            raise DomainError(
                "change_conflict",
                "Değişiklik başka bir yetkili tarafından işlendi.",
                409,
            )
        _apply_directory_config(s, config)
    from .audit import record

    record(store, "directory_change_approved", actor_id=actor.id, change_id=change_id)
    return {"status": "applied"}


def _first(value):
    return (
        value[0]
        if isinstance(value, list) and value
        else "" if value is None or value == [] else value
    )


class DirectoryClient:
    def __init__(self, config):
        self.config = config

    def connect(self, user, password):
        c = self.config
        if not c.get("host") or not user or not password:
            raise DomainError(
                "directory_not_configured",
                "Active Directory bağlantı bilgileri tamamlanmamış.",
                503,
            )
        host = c["host"]
        policy = c.get("_network_policy", {})
        if policy.get("production"):
            from .network import resolve_target

            host = resolve_target(
                c["host"],
                int(c["port"]),
                policy["allowed"],
                policy["cidrs"],
                standard_port=636 if c["transport"] == "ldaps" else 389,
            )[0]
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file=c.get("ca_file") or None,
            valid_names=[c["host"]],
            sni=c["host"],
            ssl_options=[
                ssl.OP_NO_SSLv2,
                ssl.OP_NO_SSLv3,
                ssl.OP_NO_TLSv1,
                ssl.OP_NO_TLSv1_1,
            ],
        )
        server = Server(
            host,
            port=int(c["port"]),
            use_ssl=c["transport"] == "ldaps",
            tls=tls,
            connect_timeout=10,
        )
        return Connection(
            server,
            user=user,
            password=password,
            auto_bind=(
                AUTO_BIND_NO_TLS
                if c["transport"] == "ldaps"
                else AUTO_BIND_TLS_BEFORE_BIND
            ),
            receive_timeout=15,
            raise_exceptions=True,
            auto_referrals=False,
        )

    def service(self):
        try:
            return self.connect(self.config.get("bind_dn"), self.config.get("password"))
        except LDAPBindError:
            raise DomainError(
                "directory_service_bind_failed", "AD servis hesabı doğrulanamadı.", 503
            )

    def test(self):
        with self.service() as conn:
            conn.search(
                self.config["base_dn"],
                "(objectClass=*)",
                BASE,
                attributes=["distinguishedName"],
            )
            if not conn.entries:
                raise DomainError("invalid_base_dn", "Base DN doğrulanamadı.", 503)

    @property
    def attributes(self):
        return list(
            {self.config[k] for k in self.config if k.endswith("_attribute")}
            | {"memberOf", "userAccountControl", "userPrincipalName"}
        )

    def convert(self, row):
        c = self.config
        attrs = {k.casefold(): v for k, v in row.get("attributes", {}).items()}
        raw = {k.casefold(): v for k, v in row.get("raw_attributes", {}).items()}

        def values(key):
            items = raw.get(key.casefold(), attrs.get(key.casefold(), []))
            if not isinstance(items, list):
                items = [items]
            return [x.decode("utf-8") if isinstance(x, bytes) else x for x in items]

        def value(key):
            return _first(values(key))

        guid = _first(
            raw.get(
                c["guid_attribute"].casefold(),
                attrs.get(c["guid_attribute"].casefold()),
            )
        )
        try:
            guid = (
                str(UUID(bytes_le=guid))
                if isinstance(guid, bytes) and len(guid) == 16
                else str(UUID(guid.decode() if isinstance(guid, bytes) else str(guid)))
            )
            account_control = int(value("userAccountControl"))
            username = str(value(c["username_attribute"])).casefold()
            if not username or not row.get("dn"):
                raise ValueError("missing_identity")
        except (ValueError, TypeError, UnicodeError):
            raise DomainError(
                "invalid_directory_identity",
                "AD kimlik veya hesap durumu alanı geçersiz.",
                503,
            )
        groups = values("memberOf")
        return {
            "id": "ad:" + guid.lower(),
            "username": username,
            "dn": row["dn"].casefold(),
            "manager_dn": str(value(c["manager_attribute"])).casefold(),
            "display_name": str(value(c["display_attribute"])) or username,
            "email": str(value(c["email_attribute"])),
            "department": str(value(c["department_attribute"])),
            "title": str(value(c["title_attribute"])),
            "groups": groups,
            "active": not (account_control & 2),
            "roles": [],
        }

    def authenticate(self, username, password):
        if not password:
            raise DomainError(
                "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
            )
        try:
            with self.service() as conn:
                escaped = escape_filter_chars(username)
                query = f"(&(objectCategory=person)(objectClass=user)(|({self.config['username_attribute']}={escaped})(userPrincipalName={escaped})))"
                conn.search(
                    self.config["base_dn"],
                    query,
                    SUBTREE,
                    attributes=self.attributes,
                    size_limit=2,
                )
                rows = [r for r in conn.response if r.get("type") == "searchResEntry"]
                if len(rows) != 1:
                    raise DomainError(
                        "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
                    )
                user = self.convert(rows[0])
                if not user["active"]:
                    raise DomainError(
                        "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
                    )
                with self.connect(rows[0]["dn"], password):
                    pass
                return user
        except LDAPBindError:
            raise DomainError(
                "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
            )
        except LDAPException:
            raise DomainError(
                "directory_unavailable", "Active Directory bağlantısı kurulamadı.", 503
            )

    def snapshot(self):
        try:
            with self.service() as conn:
                from itertools import islice

                rows = list(
                    islice(
                        conn.extend.standard.paged_search(
                            self.config["base_dn"],
                            "(&(objectCategory=person)(objectClass=user))",
                            SUBTREE,
                            attributes=self.attributes,
                            paged_size=500,
                            generator=True,
                        ),
                        10001,
                    )
                )
                if len(rows) > 10000:
                    raise DomainError(
                        "directory_limit",
                        "Dizin 10.000 kayıt sınırını aşıyor. Base DN kapsamını daraltın.",
                        503,
                    )
                if conn.result.get("result", 0) != 0:
                    raise DomainError(
                        "incomplete_directory", "Dizin sorgusu tamamlanamadı.", 503
                    )
                users = [
                    self.convert(r) for r in rows if r.get("type") == "searchResEntry"
                ]
                managers = {u["manager_dn"] for u in users if u["manager_dn"]}
                membership = {role: set() for role in self.config["role_groups"]}
                for role, groups in self.config["role_groups"].items():
                    for group in groups:
                        membership[role].update(
                            u["dn"]
                            for u in users
                            if group.casefold() in {g.casefold() for g in u["groups"]}
                        )
                        if self.config.get("nested_groups"):
                            nested = list(
                                islice(
                                    conn.extend.standard.paged_search(
                                        self.config["base_dn"],
                                        f"(&(objectCategory=person)(objectClass=user)(memberOf:1.2.840.113556.1.4.1941:={escape_filter_chars(group)}))",
                                        SUBTREE,
                                        attributes=[self.config["guid_attribute"]],
                                        paged_size=500,
                                        generator=True,
                                    ),
                                    10001,
                                )
                            )
                            if len(nested) > 10000 or conn.result.get("result", 0) != 0:
                                raise DomainError(
                                    "incomplete_directory",
                                    "Grup üyelikleri tamamlanamadı.",
                                    503,
                                )
                            membership[role].update(
                                row["dn"].casefold()
                                for row in nested
                                if row.get("type") == "searchResEntry"
                            )
                for user in users:
                    roles = [
                        role
                        for role, members in membership.items()
                        if user["dn"] in members
                    ]
                    if "hr" in roles:
                        user["roles"] = ["hr"]
                    elif "admin" in roles:
                        user["roles"] = ["admin"]
                    elif "manager" in roles or user["dn"] in managers:
                        user["roles"] = ["manager"]
                    else:
                        user["roles"] = ["employee"]
                return users
        except LDAPException:
            raise DomainError(
                "directory_unavailable", "Dizin eşitlemesi tamamlanamadı.", 503
            )


def synchronize(store, client_factory=DirectoryClient):
    config = directory_config(store, secret=True)
    if not config["enabled"]:
        raise DomainError(
            "directory_disabled", "Active Directory bağlantısı henüz etkin değil.", 503
        )
    users = client_factory(config).snapshot()
    if (
        not store.settings.demo
        and not directory_protected(store)
        and not any(u["active"] and "hr" in u["roles"] for u in users)
    ):
        raise DomainError(
            "missing_hr_identity",
            "İlk eşitlemede İK grubundan en az bir etkin hesap gerekli.",
            503,
        )
    by_dn = {u["dn"]: u for u in users}
    if (
        len(by_dn) != len(users)
        or len({u["id"] for u in users}) != len(users)
        or len({u["username"] for u in users}) != len(users)
    ):
        raise DomainError(
            "duplicate_directory_identity", "Dizinde yinelenen kimlik bulundu.", 503
        )
    for user in users:
        seen = {user["dn"]}
        parent = user["manager_dn"]
        while parent in by_dn:
            if parent in seen:
                raise DomainError(
                    "directory_cycle", "Dizin yönetici ilişkisinde döngü bulundu.", 503
                )
            seen.add(parent)
            parent = by_dn[parent]["manager_dn"]
    with store.cs() as s:
        known = {
            u.id: u.participant_id
            for u in s.scalars(
                select(DirectoryUser).where(DirectoryUser.source == "ldap")
            )
        }
    mapping = {}
    with store.session() as s:
        teams = {t.name.casefold(): t for t in s.scalars(select(Team))}
        for user in users:
            if not user["active"]:
                continue
            team_name = config.get("department_map", {}).get(
                user["department"], user["department"] or "Ekip eşlemesi bekliyor"
            )
            team = teams.get(team_name.casefold())
            if not team:
                team = Team(
                    name=team_name,
                    role="Rol eşlemesi bekliyor",
                    context={"purpose": ""},
                    targets=[],
                )
                s.add(team)
                s.flush()
                teams[team_name.casefold()] = team
            participant = s.get(Participant, known.get(user["id"]) or user["id"])
            if not participant:
                participant = Participant(
                    id=user["id"],
                    team_id=team.id,
                    name=user["display_name"],
                    title=user["title"] or "Rol eşlemesi bekliyor",
                )
                s.add(participant)
            participant.name = user["display_name"]
            participant.title = user["title"] or participant.title
            participant.team_id = team.id
            mapping[user["id"]] = participant.id
    stamp = time.time()
    with store.cs() as s:
        if users and not s.get(Setting, "directory_initialized"):
            s.add(Setting(key="directory_initialized", value={"initialized_at": stamp}))
        for existing in s.scalars(
            select(DirectoryUser).where(DirectoryUser.source == "ldap")
        ):
            existing.active = False
        for user in users:
            identity = s.get(DirectoryUser, user["id"])
            if not identity:
                identity = DirectoryUser(
                    id=user["id"],
                    source="ldap",
                    display_name=user["display_name"],
                    username=user["username"],
                )
                s.add(identity)
            for key in [
                "dn",
                "manager_dn",
                "display_name",
                "email",
                "roles",
                "groups",
                "active",
            ]:
                setattr(identity, key, user[key])
            identity.username = "ad:" + user["username"]
            identity.participant_id = mapping.get(user["id"]) or known.get(user["id"])
            identity.last_synced = stamp
        row = s.get(Setting, "directory_sync")
        value = {
            "last_sync": stamp,
            "users": len(users),
            "active": sum(u["active"] for u in users),
        }
        if row:
            row.value = value
        else:
            s.add(Setting(key="directory_sync", value=value))
        s.add(
            ControlEvent(
                profile_id="directory",
                action="directory_synchronized",
                detail={"users": len(users)},
            )
        )
    return value

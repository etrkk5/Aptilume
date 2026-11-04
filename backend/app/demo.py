"""Explicit presentation mode: isolated synthetic data and ordinary hashed logins."""

import json
import os
import secrets

from argon2.exceptions import VerificationError
from sqlalchemy import select

from .models import DirectoryUser, Participant, Setting
from .security import passwords, strong_password
from .store import DomainError

USERNAMES = ("hr", "employee", "admin", "manager")


def require_demo(store):
    if not store.settings.presentation_demo or not store.settings.demo:
        raise RuntimeError("Demo hesapları yalnızca APP_MODE=demo ile kullanılabilir.")


def demo_credentials(store):
    require_demo(store)
    path = store.settings.data_dir / "demo-access.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise RuntimeError("Demo erişim dosyası yok veya geçersiz; bootstrap gerekli.")
    accounts = json.loads(path.read_text())
    if (
        not isinstance(accounts, dict)
        or set(accounts) != set(USERNAMES)
        or any(not strong_password(value) for value in accounts.values())
    ):
        raise RuntimeError("Demo erişim dosyasının biçimi geçersiz.")
    return accounts


def prepare_demo(store):
    require_demo(store)
    # No custom control store or arbitrary DB profile can be inherited from production.
    root = store.settings.data_dir
    if str(store.control.url) != f"sqlite:///{root / 'control.db'}":
        raise RuntimeError("Sunum için izole yerel kontrol deposu gerekli.")
    with store.cs() as s:
        if s.get(Setting, "presentation_demo"):
            demo_credentials(store)
            return
        if s.scalar(select(DirectoryUser.id).limit(1)):
            raise RuntimeError("Sunum kurulumu boş bir kimlik deposu gerektirir.")
    from .models import Binding, ProfileVersion

    with store.cs() as s:
        version = s.get(ProfileVersion, s.get(Binding, "application_db").version_id)
        if version.config != {"engine": "sqlite", "path": str(root / "application.db")}:
            raise RuntimeError("Sunum için izole yerel uygulama deposu gerekli.")
        for purpose in ("generation", "evaluation", "insights"):
            version = s.get(ProfileVersion, s.get(Binding, purpose).version_id)
            if version.config.get("provider") != "mock":
                raise RuntimeError("İlk sunum kurulumu mock LLM gerektirir.")
    path = root / "demo-access.json"
    if not path.exists():
        accounts = {}
        for username in USERNAMES:
            while True:
                value = "Apti!" + secrets.token_urlsafe(12)
                if strong_password(value):
                    accounts[username] = value
                    break
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o640)
        with os.fdopen(fd, "w") as f:
            json.dump(accounts, f)
    accounts = demo_credentials(store)
    from .cli import seed

    seed(store)
    with store.session() as s:
        people = list(s.scalars(select(Participant)))
    with store.cs() as s:
        for person in people:
            leader = person.id.endswith("-person-01")
            username = (
                "manager"
                if person.id == "team-data-person-01"
                else (
                    "employee"
                    if person.id == "team-data-person-02"
                    else "person." + person.id
                )
            )
            s.add(
                DirectoryUser(
                    id="demo:" + person.id,
                    username=username,
                    display_name=person.name,
                    roles=["manager" if leader else "employee"],
                    groups=[],
                    source="demo",
                    participant_id=person.id,
                    dn=f"cn={person.id},ou=presentation",
                    manager_dn=(
                        ""
                        if leader
                        else f"cn={person.team_id}-person-01,ou=presentation"
                    ),
                    password_hash=(
                        passwords.hash(accounts[username])
                        if username in accounts
                        else None
                    ),
                )
            )
        for username, role, name in (
            ("hr", "hr", "İnsan Kaynakları"),
            ("admin", "admin", "Entegrasyon yöneticisi"),
        ):
            s.add(
                DirectoryUser(
                    id="demo:" + username,
                    username=username,
                    display_name=name,
                    roles=[role],
                    groups=[],
                    source="demo",
                    password_hash=passwords.hash(accounts[username]),
                )
            )
        s.add(Setting(key="presentation_demo", value={"version": 1}))


def authenticate_demo(store, username, password):
    require_demo(store)
    with store.cs() as s:
        identity = s.scalar(
            select(DirectoryUser).where(
                DirectoryUser.username == username.casefold(),
                DirectoryUser.source == "demo",
            )
        )
    # All attempts pay the normal password verification cost, including unknown names.
    with store.cs() as s:
        fallback = s.get(DirectoryUser, "demo:admin")
    encoded = (
        identity.password_hash
        if identity and identity.active and identity.password_hash
        else fallback.password_hash
    )
    try:
        verified = passwords.verify(encoded, password)
    except VerificationError:
        verified = False
    if (
        not verified
        or not identity
        or not identity.active
        or not identity.password_hash
    ):
        raise DomainError(
            "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
        )
    return identity.id

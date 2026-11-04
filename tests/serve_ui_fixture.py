"""Isolated UI QA fixture; never part of the runtime image or production auth."""

import os
import tempfile
from uuid import UUID
from fastapi import FastAPI
import uvicorn
from app.api import create_app
from app.cli import seed
from app.config import Settings
from app.directory import save_directory_config
from app.models import DirectoryUser
from app.security import AuthService
from app.store import Store, DomainError


def main():
    path = tempfile.TemporaryDirectory(prefix="aptilume-ui-")
    from pathlib import Path

    data = Path(path.name).resolve()
    store = Store(Settings(data, f"sqlite:///{data/'control.db'}"))
    seed(store)
    roles = [
        ("manager", "manager", 1, ""),
        ("other-manager", "manager", 2, ""),
        ("employee", "employee", 3, "manager"),
        ("other-employee", "employee", 4, "other-manager"),
        ("hr", "hr", 5, ""),
    ]
    rows = []
    with store.cs() as s:
        for i, (name, role, pid, parent) in enumerate(roles, 1):
            identity = "ad:" + str(UUID(int=i))
            s.add(
                DirectoryUser(
                    id=identity,
                    username="ad:" + name,
                    display_name="Test " + name,
                    roles=[role],
                    groups=[],
                    source="ldap",
                    participant_id=f"team-data-person-{pid:02}",
                    dn=f"cn={name}",
                    manager_dn=f"cn={parent}" if parent else "",
                )
            )
            rows.append(
                dict(
                    id=identity,
                    username=name,
                    display_name="Test " + name,
                    email=name + "@example.test",
                    department="Data & Analytics",
                    title="Engineer",
                    groups=[],
                    roles=[role],
                    active=True,
                    dn=f"cn={name}",
                    manager_dn=f"cn={parent}" if parent else "",
                )
            )

    class FixtureDirectory:
        def __init__(self, config):
            pass

        def snapshot(self):
            return rows

        def authenticate(self, username, password):
            if password == "fixture-password":
                for row in rows:
                    if row["username"] == username:
                        return row
            raise DomainError(
                "invalid_credentials", "Kullanıcı adı veya parola hatalı.", 401
            )

        def test(self):
            pass

    save_directory_config(
        store,
        {
            "enabled": True,
            "host": "fixture.example.test",
            "base_dn": "dc=example,dc=test",
            "bind_dn": "cn=service",
            "password": "fixture-only",
        },
    )
    auth = AuthService(store, FixtureDirectory)
    uvicorn.run(create_app(store=store, auth_service=auth), host="127.0.0.1", port=8090)
    path.cleanup()


if __name__ == "__main__":
    main()

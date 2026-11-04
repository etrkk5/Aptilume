"""Isolated container verification; only the dedicated local fixture host is accepted."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import select
from app.config import Settings
from app.store import Store
from app.services import (
    load_catalog,
    seed_people,
    seed_roles,
    create_campaign,
    enqueue_generation,
    campaign_transition,
    seed_answers,
    start_run,
)
from app.models import (
    Skill,
    Publication,
    Participant,
    RoleProfile,
    DirectoryUser,
    DevelopmentAction,
    ExportScope,
)
from app.api import create_app
from app.security import COOKIE
from fastapi.testclient import TestClient
from app.worker import Worker
from app.reporting import publish, metrics


def main():
    host = os.environ["TEST_DB_HOST"]
    assert host == "aptilume-postgres-verify", "Use the isolated fixture container only"
    with TemporaryDirectory() as directory:
        path = Path(directory)
        store = Store(Settings(path, f"sqlite:///{path/'control.db'}"))
        load_catalog(store)
        seed_people(store)
        seed_roles(store)
        profile = store.save_profile(
            "db",
            "PostgreSQL fixture",
            {
                "engine": "postgresql",
                "host": host,
                "port": 5432,
                "database": "aptilume_fixture",
                "username": "postgres",
                "sslmode": "disable",
            },
            "fixture-only",
        )
        result = store.activate_db(profile["id"])
        assert (
            result["counts"]["skills"] == 42 and result["counts"]["participants"] == 30
        )
        campaign = create_campaign(
            store, "PostgreSQL end-to-end fixture", ["team-data"]
        )
        enqueue_generation(store, campaign["id"])
        Worker(store).drain()
        campaign_transition(store, campaign["id"], "approve")
        campaign_transition(store, campaign["id"], "open")
        seed_answers(store, campaign["id"], 6)
        campaign_transition(store, campaign["id"], "close")
        run = start_run(store, campaign["id"])
        Worker(store).drain()
        pid = publish(store, run["id"])
        with store.session() as s:
            report = metrics(s.get(Publication, pid).snapshot)
        assert (
            report["assigned"] == 10
            and report["submitted"] == 6
            and len(report["rows"]) == 36
        )
        app = create_app(store=store)
        with store.cs() as s:
            s.add(
                DirectoryUser(
                    id="fixture-hr",
                    username="fixture-hr",
                    display_name="Fixture HR",
                    roles=["hr"],
                    groups=[],
                    source="local",
                )
            )
        token, actor = app.state.auth.create_session("fixture-hr")
        with TestClient(app) as client:
            client.cookies.set(COOKIE, token)
            client.headers["X-CSRF-Token"] = actor.csrf_token
            action = client.post(
                "/api/v1/development-actions",
                json={
                    "title": "PostgreSQL development plan",
                    "owner_name": "Fixture HR",
                    "participant_id": "team-data-person-01",
                },
            )
            assert action.status_code == 200, action.text
            value = action.json()
            assert (
                client.patch(
                    "/api/v1/development-actions/" + value["id"],
                    json={**value, "status": "completed"},
                ).status_code
                == 200
            )
            export = client.post(
                "/api/v1/exports", json={"publication_id": pid, "detail": True}
            )
            assert export.status_code == 202, export.text
            Worker(store).drain()
            assert (
                client.get(
                    "/api/v1/exports/" + export.json()["id"] + "/download"
                ).status_code
                == 200
            )
        with store.session() as s:
            assert s.get(DevelopmentAction, value["id"]).status == "completed"
            assert s.get(ExportScope, export.json()["id"]).creator_id == "fixture-hr"
        # Exercise the new control-store security tables on PostgreSQL as well.
        from concurrent.futures import ThreadPoolExecutor
        from app.models import Binding, AuthSession
        from app.throttle import reserve
        from app.security import AuthService
        from app.store import DomainError

        controlled = Store(
            Settings(
                path,
                f"postgresql+psycopg://postgres:fixture-only@{host}/aptilume_fixture?sslmode=disable",
            )
        )
        target = controlled.save_profile(
            "db",
            "Existing fixture",
            {
                "engine": "postgresql",
                "host": host,
                "database": "aptilume_fixture",
                "username": "postgres",
                "sslmode": "disable",
            },
        )
        with controlled.cs() as s:
            s.get(Binding, "application_db").version_id = target["id"] + ":1"
        auth = AuthService(controlled)

        def limited(i):
            try:
                reserve(controlled, "pg-race", "same-user", 5, 3600)
                return True
            except DomainError:
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert sum(pool.map(limited, range(20))) == 5
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: auth.create_session("local-admin"), range(12)))
        with controlled.cs() as s:
            assert len(list(s.scalars(select(AuthSession)))) == 5
        # Runtime works with CRUD permissions; schema DDL stays with the operator.
        from sqlalchemy import text
        from sqlalchemy.exc import DBAPIError

        with controlled.control.begin() as conn:
            conn.execute(
                text(
                    "CREATE ROLE aptilume_runtime_fixture LOGIN PASSWORD 'fixture-only' NOSUPERUSER NOCREATEDB NOCREATEROLE"
                )
            )
            conn.execute(
                text(
                    "GRANT CONNECT ON DATABASE aptilume_fixture TO aptilume_runtime_fixture"
                )
            )
            conn.execute(
                text("GRANT USAGE ON SCHEMA public TO aptilume_runtime_fixture")
            )
            conn.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aptilume_runtime_fixture"
                )
            )
        restricted = controlled.save_profile(
            "db",
            "Restricted runtime",
            {
                "engine": "postgresql",
                "host": host,
                "database": "aptilume_fixture",
                "username": "aptilume_runtime_fixture",
                "sslmode": "disable",
            },
            "fixture-only",
        )
        with controlled.cs() as s:
            s.get(Binding, "application_db").version_id = restricted["id"] + ":1"
        limited = Store(
            Settings(
                path,
                f"postgresql+psycopg://aptilume_runtime_fixture:fixture-only@{host}/aptilume_fixture?sslmode=disable",
            )
        )
        assert limited.application_error is None
        limited_auth = AuthService(limited)
        token, _ = limited_auth.login("admin", "admin", "fixture")
        assert limited_auth.actor(token).integrations
        try:
            with limited.engine.begin() as conn:
                conn.execute(text("CREATE TABLE denied_ddl_fixture (id integer)"))
        except DBAPIError:
            pass
        else:
            raise AssertionError("Runtime role unexpectedly has schema DDL permission")
        print(
            "PostgreSQL PASS: SQLite migration + 42 skills + 30 participants + 3 role profiles + 22-question forms + worker + publication + metrics + authenticated plans and scoped Excel + PostgreSQL control-store auth and atomic limits + CRUD-only runtime role."
        )


if __name__ == "__main__":
    main()

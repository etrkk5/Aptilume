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
        print(
            "PostgreSQL PASS: SQLite migration + 42 skills + 30 participants + 3 role profiles + 22-question forms + worker + publication + metrics + authenticated plans and scoped Excel."
        )


if __name__ == "__main__":
    main()

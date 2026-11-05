"""Isolated container verification; only the dedicated local fixture host is accepted."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import select
from app.config import Settings
from app.store import Store, engine_for
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


def check_initial_postgres_install(host):
    """One Secret URL stores both domains; bootstrap must be safe to repeat."""
    import subprocess
    from unittest.mock import patch
    from cryptography.fernet import Fernet
    from sqlalchemy import text
    from app.security import AuthService
    from app.models import Binding, ProfileVersion

    base_url = f"postgresql+psycopg://postgres:fixture-only@{host}/aptilume_fixture"
    owner = engine_for(base_url)
    with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("CREATE DATABASE aptilume_first_install_fixture"))
    try:
        with (
            TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {
                    # Synthetic fixture deliberately uses test TLS policy, never production.
                    "APP_MODE": "test",
                    "DATA_DIR": directory,
                    "DATABASE_URL": base_url.replace(
                        "/aptilume_fixture",
                        "/aptilume_first_install_fixture?sslmode=disable",
                    ),
                    "CONTROL_STORE_URL": "",
                    "BOOTSTRAP_ADMIN_PASSWORD": "Fixture-integration-47!",
                    "BOOTSTRAP_HR_PASSWORD": "Fixture-people-58!",
                    "SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
                },
            ),
        ):
            for _ in range(2):
                subprocess.run(
                    ["python", "-m", "app.cli", "bootstrap"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            store = Store(Settings.from_env())
            assert store.application_error is None
            assert (
                store.control.url.database
                == store.engine.url.database
                == "aptilume_first_install_fixture"
            )
            assert store.control.url.get_backend_name() == "postgresql"
            assert not list(Path(directory).glob("*.db"))
            with store.session() as session:
                assert len(list(session.scalars(select(Skill)))) == 42
                assert not list(session.scalars(select(Participant)))
            auth = AuthService(store)
            assert auth.login("hr", "Fixture-people-58!", "fixture-hr")[1].hr
            assert auth.login("admin", "Fixture-integration-47!", "fixture-admin")[
                1
            ].roles == {"admin"}
            with store.cs() as session:
                assert len(list(session.scalars(select(DirectoryUser)))) == 2
                binding = session.get(Binding, "application_db")
                version = session.get(ProfileVersion, binding.version_id)
                assert version.config["engine"] == "postgresql"
                assert store.decrypt(version.secret) == "fixture-only"
            store.engine.dispose()
            store.control.dispose()
    finally:
        with owner.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text("DROP DATABASE aptilume_first_install_fixture WITH (FORCE)")
            )
        owner.dispose()


def main():
    host = os.environ["TEST_DB_HOST"]
    assert host == "aptilume-postgres-verify", "Use the isolated fixture container only"
    check_initial_postgres_install(host)
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
        # HR instruction version CAS and JSON cohort filters on PostgreSQL,
        # using the same CRUD-only role as the runtime.
        with limited.cs() as s:
            s.add(
                DirectoryUser(
                    id="pg-policy-hr",
                    username="pg-policy-hr",
                    display_name="Fixture HR",
                    roles=["hr"],
                    groups=[],
                    source="local",
                )
            )
        hr_token, hr_actor = limited_auth.create_session("pg-policy-hr")
        with TestClient(create_app(store=limited)) as c:
            c.cookies.set(COOKIE, hr_token)
            c.headers["X-CSRF-Token"] = hr_actor.csrf_token
            active = c.get("/api/v1/prompt-policies").json()["active"]
            changed = {
                k: v + " PostgreSQL fixture policy."
                for k, v in active["instructions"].items()
            }
            response = c.post(
                "/api/v1/prompt-policies",
                json={"expected_version": active["version"], "instructions": changed},
            )
            assert (
                response.status_code == 201
                and response.json()["version"] == active["version"] + 1
            )
            assert (
                c.post(
                    "/api/v1/prompt-policies",
                    json={
                        "expected_version": active["version"],
                        "instructions": changed,
                    },
                ).status_code
                == 409
            )
            quality_campaign = create_campaign(
                limited,
                "PG Quality fixture",
                ["team-data"],
                participant_ids=["team-data-person-02"],
            )["id"]
            enqueue_generation(limited, quality_campaign)
            Worker(limited).drain()
            campaign_transition(limited, quality_campaign, "approve")
            campaign_transition(limited, quality_campaign, "open")
            from app.services import assignments, form, save_answer, submit

            aid = assignments(limited, quality_campaign)[0]["id"]
            first = True
            for question in form(limited, aid)["questions"]:
                if question["type"] == "open_text":
                    value = {
                        "text": (
                            "asdfasdf"
                            if first
                            else "Kaynakları kontrol eder ve bağımsız verilerle doğrularım."
                        ),
                        "revision": 0,
                    }
                    first = False
                else:
                    value = {
                        "selected": [
                            "none" if question["type"] == "self_assessment" else "b"
                        ],
                        "revision": 0,
                    }
                save_answer(limited, aid, question["id"], value)
            submit(limited, aid)
            campaign_transition(limited, quality_campaign, "close")
            start_run(limited, quality_campaign)
            Worker(limited).drain()
            body = c.get(
                "/api/v1/quality-cases",
                params={"team_id": "team-data", "campaign_id": quality_campaign},
            ).json()
            assert body["total"] >= 1 and body["summary"]["people"] == 1
            for case in body["items"]:
                detail = c.get("/api/v1/quality-cases/" + case["id"]).json()
                assert detail["category"] == "nonsensical" and detail["can_review"]
                assert (
                    c.post(
                        "/api/v1/reviews/" + case["evaluation_id"] + "/decision",
                        json={"score": 0, "reason": "Fixture HR quality decision."},
                    ).status_code
                    == 200
                )
            Worker(limited).drain()
            assert (
                c.get(
                    "/api/v1/quality-cases", params={"campaign_id": quality_campaign}
                ).json()["summary"]["pending"]
                == 0
            )
            # Catalog uses JSON versions and legacy period snapshots with CRUD only.
            from app.models import Campaign

            with limited.session() as session:
                legacy = session.get(Campaign, campaign["id"])
                legacy.config = {
                    k: v for k, v in legacy.config.items() if k != "skill_snapshots"
                }
            old = next(
                row
                for row in c.get("/api/v1/skills").json()
                if row["id"] == "SKILL-005"
            )
            payload = {
                k: old[k]
                for k in (
                    "code",
                    "name",
                    "definition",
                    "levels",
                    "owners",
                    "domain",
                    "family",
                    "owner_department",
                )
            }
            response = c.patch(
                "/api/v1/skills/SKILL-005",
                json={
                    **payload,
                    "name": "PostgreSQL catalog edit",
                    "expected_version": 1,
                },
            )
            assert response.status_code == 200, response.text
            assert (
                c.patch(
                    "/api/v1/skills/SKILL-005", json={**payload, "expected_version": 1}
                ).status_code
                == 409
            )
            with limited.session() as session:
                assert (
                    session.get(Campaign, campaign["id"]).config["skill_snapshots"][
                        "SKILL-005"
                    ]["name"]
                    == old["name"]
                )
                assert session.get(Publication, pid).snapshot["rows"] == report["rows"]
            created = c.post(
                "/api/v1/skills",
                json={**payload, "code": 70, "name": "PostgreSQL new skill"},
            )
            assert created.status_code == 201, created.text
            assert (
                c.delete("/api/v1/skills/SKILL-070?expected_version=1").status_code
                == 200
            )
            assert c.get("/api/v1/catalog/skills?status=archived").json()["total"] == 1
            assert (
                c.post(
                    "/api/v1/skills/SKILL-070/restore?expected_version=2"
                ).status_code
                == 200
            )
            # HR question drafting and publication, with the CRUD-only PG role.
            editable_id = create_campaign(
                limited, "PG editable question set", ["team-data"]
            )["id"]
            enqueue_generation(limited, editable_id)
            Worker(limited).drain()
            prefix = f"/api/v1/campaigns/{editable_id}"
            editor = c.get(prefix + "/question-set").json()
            question = next(
                q
                for q in editor["questions"]
                if q["type"] == "open_text" and q["form_key"] == "common"
            )
            body = {
                k: question[k]
                for k in (
                    "form_key",
                    "skill_id",
                    "type",
                    "prompt",
                    "options",
                    "rubric",
                    "reference",
                    "evidence_type",
                )
            }
            response = c.patch(
                prefix + "/questions/" + question["id"],
                json={
                    **body,
                    "prompt": "PG HR question correction",
                    "expected_version": editor["version"],
                },
            )
            assert response.status_code == 200, response.text
            editor = response.json()
            stale = editor["version"]
            response = c.post(
                prefix + "/questions",
                json={
                    **body,
                    "prompt": "PG extra common question",
                    "expected_version": stale,
                },
            )
            assert response.status_code == 201, response.text
            editor = response.json()
            assert (
                c.patch(
                    prefix + "/questions/" + question["id"],
                    json={**body, "expected_version": stale},
                ).status_code
                == 409
            )
            mcq = next(q for q in editor["questions"] if q["type"] == "single_choice")
            response = c.delete(
                prefix + "/questions/" + mcq["id"],
                params={"expected_version": editor["version"]},
            )
            assert response.status_code == 200, response.text
            editor = response.json()
            approved = c.post(
                prefix + "/approve", json={"expected_version": editor["version"]}
            )
            assert approved.status_code == 200, approved.text
            opened = c.post(
                prefix + "/open",
                json={"expected_version": approved.json()["row_version"]},
            )
            assert opened.status_code == 200, opened.text
            assert (
                c.patch(
                    prefix + "/questions/" + question["id"],
                    json={**body, "expected_version": opened.json()["row_version"]},
                ).status_code
                == 409
            )
            seed_answers(limited, editable_id, 6)
            campaign_transition(limited, editable_id, "close")
            editor_run = start_run(limited, editable_id)
            Worker(limited).drain()
            editor_publication = publish(limited, editor_run["id"])
            with limited.session() as session:
                snapshot = session.get(Publication, editor_publication).snapshot
                assert snapshot["question_approval"]["actor_id"] == "pg-policy-hr"
                written_rows = [
                    r for r in snapshot["rows"] if r["skill_id"] == question["skill_id"]
                ]
                assert written_rows and all(
                    r["expected_written_questions"] == 3 and r["coverage"] == 1
                    for r in written_rows
                )
        print(
            "PostgreSQL PASS: SQLite migration + 42 skills + 30 participants + 3 role profiles + 22-question forms + worker + publication + metrics + authenticated plans and scoped Excel + PostgreSQL control-store auth and atomic limits + CRUD-only runtime role + HR policy versioning, quality decisions and catalog CRUD/snapshots and HR question authoring/approval/publication with variable scoring."
        )


if __name__ == "__main__":
    main()

"""English defaults, explicit Turkish, immutable assessment language and evidence."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.api import create_app
from app.models import Campaign, Question
from app.services import create_campaign, enqueue_generation
from app.worker import Worker
from app.providers import Provider
from app.quality import explicit_no_experience


def test_default_and_turkish_error_responses_are_localized_without_echoing_secrets(
    store,
):
    with TestClient(create_app(store=store)) as client:
        for language, expected in [
            ("en", "Incorrect username or password."),
            ("tr", "Kullanıcı adı veya parola hatalı."),
        ]:
            response = client.post(
                "/api/v1/auth/login",
                json={"username": "unknown", "password": "never-echo-this-value"},
                headers={"X-Aptilume-Language": language},
            )
            assert (
                response.status_code == 401 and response.json()["message"] == expected
            )
            assert response.headers["content-language"] == language
            assert "never-echo" not in response.text
        response = client.post(
            "/api/v1/auth/login", json={"username": "unknown", "password": "wrong"}
        )
        assert response.json()["message"] == "Incorrect username or password."


def test_new_assessment_uses_selected_language_and_existing_period_keeps_it(
    client, store
):
    english = client.post("/api/v1/campaigns", json={"name": "English period"}).json()
    turkish = client.post(
        "/api/v1/campaigns",
        json={"name": "Turkish period"},
        headers={"X-Aptilume-Language": "tr"},
    ).json()
    assert english["config"]["language"] == "en"
    assert turkish["config"]["language"] == "tr"
    for campaign in [english, turkish]:
        enqueue_generation(store, campaign["id"])
    Worker(store).drain()
    with store.session() as session:
        en_questions = list(
            session.scalars(
                select(Question).where(Question.campaign_id == english["id"])
            )
        )
        tr_questions = list(
            session.scalars(
                select(Question).where(Question.campaign_id == turkish["id"])
            )
        )
        assert en_questions and tr_questions
        assert all(not set("ıİşŞçÇğĞöÖüÜ") & set(q.prompt) for q in en_questions)
        assert any("açıklayın" in q.prompt for q in tr_questions)
        assert any("Explain your approach" in q.prompt for q in en_questions)
    client.get("/api/v1/bootstrap", headers={"X-Aptilume-Language": "en"})
    with store.session() as session:
        assert session.get(Campaign, turkish["id"]).config["language"] == "tr"
    assert (
        client.post(
            "/api/v1/campaigns", json={"name": "Invalid", "language": "fr"}
        ).status_code
        == 422
    )


def test_legacy_period_without_language_retains_turkish_content(store):
    campaign = create_campaign(store, "Legacy period")
    with store.session() as session:
        row = session.get(Campaign, campaign["id"])
        row.config = {
            key: value for key, value in row.config.items() if key != "language"
        }
    enqueue_generation(store, campaign["id"])
    Worker(store).drain()
    with store.session() as session:
        assert any(
            "açıklayın" in q.prompt
            for q in session.scalars(
                select(Question).where(Question.campaign_id == campaign["id"])
            )
        )


def test_english_honest_no_experience_is_zero_rubric_points():
    answer = "I have no experience yet."
    assert explicit_no_experience(answer)
    provider = Provider({"provider": "mock", "model": "fixture"})
    value, _ = provider.complete(
        "grade", {"language": "en", "answer": answer, "rubric": [{"id": "c1"}]}
    )
    assert value["criteria"][0]["points"] == 0
    assert value["criteria"][0]["evidence_quotes"] == []
    assert value["quality"]["category"] == "no_experience"
    assert "Synthetic" in value["criteria"][0]["reason"]


def test_export_headers_follow_queued_language_and_responses_are_preserved(
    client, store
):
    from openpyxl import load_workbook
    from test_access import publication
    from app.models import Export

    _, _, published = publication(store)
    exported_content = []
    for language, title, header in [
        ("en", "Responses", "Response ID"),
        ("tr", "Yanitlar", "Yanıt ID"),
    ]:
        response = client.post(
            "/api/v1/exports",
            json={"publication_id": published, "detail": True},
            headers={"X-Aptilume-Language": language},
        )
        assert response.status_code == 202
        client.headers["X-Aptilume-Language"] = "en" if language == "tr" else "tr"
        Worker(store).drain()
        with store.session() as session:
            record = session.get(Export, response.json()["id"])
            workbook = load_workbook(record.file, data_only=True)
            assert workbook[title].cell(1, 1).value == header
            assert workbook[title].max_row > 1
            rows = list(workbook[title].iter_rows(min_row=2, values_only=True))
            assert any(row[4] for row in rows if row[2] == "open_text")
            exported_content.append(
                sorted((row[0], row[3], row[4] or "") for row in rows)
            )
    assert exported_content[0] == exported_content[1]

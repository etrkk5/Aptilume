import argparse
import os
from sqlalchemy import select
from .config import Settings
from .store import Store
from .models import Campaign
from .services import (
    load_catalog,
    seed_people,
    seed_roles,
    create_campaign,
    enqueue_generation,
    campaign_transition,
    seed_answers,
    start_run,
)
from .worker import Worker
from .reporting import publish


def seed(store):
    load_catalog(store)
    seed_people(store)
    seed_roles(store)
    with store.session() as s:
        if s.scalar(select(Campaign.id)):
            return
    w = Worker(store)
    closed = create_campaign(store, "AI Skills Baseline · Kasım 2026")
    enqueue_generation(store, closed["id"])
    w.drain()
    campaign_transition(store, closed["id"], "approve")
    campaign_transition(store, closed["id"], "open")
    seed_answers(store, closed["id"], 24)
    campaign_transition(store, closed["id"], "close")
    r = start_run(store, closed["id"])
    w.drain()
    publish(store, r["id"])
    live = create_campaign(store, "AI Readiness Pulse · Pilot")
    enqueue_generation(store, live["id"])
    w.drain()
    campaign_transition(store, live["id"], "approve")
    campaign_transition(store, live["id"], "open")
    print("Aptilume demo hazır: 42 yetkinlik, 30 sentetik kişi, 2 kampanya.")


def main():
    p = argparse.ArgumentParser(description="Aptilume runtime")
    p.add_argument(
        "command", choices=["api", "worker", "bootstrap", "seed", "migrate", "drain"]
    )
    args = p.parse_args()
    store = Store(Settings.from_env())
    if args.command == "bootstrap":
        load_catalog(store)
        from .security import AuthService

        AuthService(store)
        print("Katalog ve ilk kurulum hesabı hazır.")
    elif args.command == "seed":
        if not store.settings.demo:
            raise RuntimeError("Örnek veri üretimi üretim ortamında kapalı.")
        seed(store)
    elif args.command == "api":
        import uvicorn
        from .api import create_app

        uvicorn.run(
            create_app(store=store),
            host=os.getenv("APP_HOST", "0.0.0.0"),
            port=int(os.getenv("APP_PORT", "8080")),
        )
    elif args.command == "worker":
        Worker(store).run()
    elif args.command == "drain":
        print(Worker(store).drain())
    else:
        from alembic.config import Config
        from alembic import command
        from .config import ROOT

        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "backend/migrations"))
        with store.engine.connect() as conn:
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
        print("Şema en son sürüme yükseltildi.")


if __name__ == "__main__":
    main()

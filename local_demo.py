"""Run the isolated local demo with Python and a prebuilt web interface."""

import argparse
import os
from pathlib import Path
import sys


def configure(root, port):
    """Explicit demo settings; never reuse a corporate database or LAN bind."""
    os.environ.update(
        APP_MODE="demo",
        DATA_DIR=str(root / "runtime"),
        REFERENCE_DIR=str(root / "data"),
        APP_HOST="127.0.0.1",
        APP_PORT=str(port),
        PUBLIC_BASE_URL=f"http://127.0.0.1:{port}",
        FORWARDED_ALLOW_IPS="",
    )


def main(argv=None):
    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 veya daha yeni bir sürüm gerekli.")
    parser = argparse.ArgumentParser(
        description="Aptilume: hazır arayüzle, yalnız Python kullanan yerel demo."
    )
    parser.add_argument(
        "command", choices=["setup", "accounts", "api", "worker", "quality-sample"]
    )
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Port 1024–65535 aralığında olmalı.")
    root = Path(__file__).resolve().parent
    if args.command == "api" and not all(
        path.exists()
        for path in [
            root / "web/dist/index.html",
            root / "web/dist/assets",
            root / "web/dist/brand/yapi-kredi-logo.svg",
        ]
    ):
        parser.error(
            "Hazır arayüz bulunamadı. Python paketini ZIP'ten tamamen çıkarın; "
            "web/dist klasörü de bulunmalı."
        )
    configure(root, args.port)
    sys.path.insert(0, str(root / "backend"))
    from app.cli import main as application

    commands = {
        "setup": "bootstrap",
        "accounts": "demo-accounts",
        "quality-sample": "demo-quality-sample",
    }
    previous = sys.argv
    try:
        sys.argv = ["aptilume", commands.get(args.command, args.command)]
        application()
    finally:
        sys.argv = previous


if __name__ == "__main__":
    # Windows locale defaults must not change catalog/instruction file encoding.
    if not sys.flags.utf8_mode:
        os.execv(
            sys.executable,
            [
                sys.executable,
                "-X",
                "utf8",
                str(Path(__file__).resolve()),
                *sys.argv[1:],
            ],
        )
    main()

"""Package Python sources and prebuilt browser files; omit local data and secrets."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib
import zipfile


def package(root, output):
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    dist = root / "web/dist"
    if not (dist / "index.html").is_file() or not (dist / "assets").is_dir():
        raise RuntimeError("Önce güvenilen build ortamında web arayüzünü derleyin.")
    files = {
        "local_demo.py": root / "local_demo.py",
        "requirements.lock.txt": root / "requirements.lock.txt",
        "alembic.ini": root / "alembic.ini",
        "pyproject.toml": root / "pyproject.toml",
        "README.md": root / "docs/LOCAL_PYTHON.md",
    }
    for directory, pattern in (
        (root / "backend", "*.py"),
        (root / "data", "*.json"),
        (dist, "*"),
    ):
        for source in directory.rglob(pattern):
            if source.is_file() and "__pycache__" not in source.parts:
                if source.is_symlink() or not source.resolve().is_relative_to(root):
                    raise RuntimeError(
                        "Paket kaynağı proje içinde normal dosya olmalı."
                    )
                files[source.relative_to(root).as_posix()] = source
    prefix = f"Aptilume-{version}-Python"
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    manifest = {
        "application": "Aptilume",
        "version": version,
        "source_commit": commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": "Python >=3.12; browser; pip dependencies in requirements.lock.txt",
        "files": {},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for target, source in sorted(files.items()):
            body = source.read_bytes()
            archive.writestr(f"{prefix}/{target}", body)
            manifest["files"][target] = hashlib.sha256(body).hexdigest()
        archive.writestr(
            f"{prefix}/PACKAGE.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = package(Path(__file__).resolve().parents[1], args.output.resolve())
    print(f"{len(result['files'])} dosya hazır: {args.output}")

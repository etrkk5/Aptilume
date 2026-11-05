"""A prebuilt browser bundle runs with isolated Python-only demo settings."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(path):
    spec = importlib.util.spec_from_file_location("python_bundle_test", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def bundle_tree(tmp_path):
    files = {
        "pyproject.toml": '[project]\nversion="0.5.0"\n',
        "requirements.lock.txt": "fixture==1.0\n",
        "alembic.ini": "[alembic]\n",
        "local_demo.py": "# Launcher\n",
        "docs/LOCAL_PYTHON.md": "# Python demo\n",
        "backend/app/api.py": "# API\n",
        "backend/migrations/env.py": "# Migration\n",
        "data/catalog.json": "{}",
        "web/dist/index.html": '<script src="/assets/site.js"></script>',
        "web/dist/assets/site.js": "console.log('prebuilt')",
        "web/dist/brand/yapi-kredi-logo.svg": "<svg/>",
        ".env": "DO_NOT_EXPORT=secret",
        "runtime/presentation-demo/demo-access.json": '{"password":"secret"}',
        "backend/app/__pycache__/cached.py": "# Never package cached files",
        "web/node_modules/node/secret.txt": "# Never package dependencies",
        ".venv/secret.txt": "# Never package installed runtime",
    }
    for name, body in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    return tmp_path


def test_package_omits_local_secrets_and_installed_runtimes(bundle_tree, monkeypatch):
    builder = module(ROOT / "scripts/package_python.py")
    monkeypatch.setattr(
        builder.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(stdout="fixture-source-commit\n"),
    )
    output = bundle_tree / "output.zip"
    builder.package(bundle_tree, output)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        prefix = "Aptilume-0.5.0-Python/"
        manifest = json.loads(archive.read(prefix + "PACKAGE.json"))
        assert manifest["source_commit"] == "fixture-source-commit"
        assert prefix + "web/dist/assets/site.js" in names
        assert prefix + "backend/migrations/env.py" in names
        assert prefix + "README.md" in names
        assert not any(
            token in name
            for token in (".env", ".venv", "runtime/", "node_modules", "__pycache__")
            for name in names
        )
        for path, digest in manifest["files"].items():
            assert hashlib.sha256(archive.read(prefix + path)).hexdigest() == digest


def test_package_requires_prebuilt_interface(bundle_tree):
    (bundle_tree / "web/dist/index.html").unlink()
    builder = module(ROOT / "scripts/package_python.py")
    with pytest.raises(RuntimeError, match="arayüzünü derleyin"):
        builder.package(bundle_tree, bundle_tree / "output.zip")


def test_launcher_never_inherits_production_store_or_network_bind(
    tmp_path, monkeypatch
):
    launcher = module(ROOT / "local_demo.py")
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setenv("APP_MODE", "production")
    monkeypatch.setenv("DATA_DIR", "/production-data")
    monkeypatch.setenv("APP_HOST", "0.0.0.0")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://corporate.example")
    monkeypatch.setenv("CONTROL_STORE_URL", "postgresql://production.example/db")
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "must-not-be-used")
    launcher.configure(tmp_path, 8091)
    from app.config import Settings

    settings = Settings.from_env()
    assert settings.presentation_demo and settings.demo
    assert settings.data_dir == tmp_path / "runtime/presentation-demo"
    assert "production.example" not in settings.control_url
    assert settings.secret_key is None
    assert settings.public_base_url == "http://127.0.0.1:8091"
    assert os.environ["APP_HOST"] == "127.0.0.1"
    assert os.environ["FORWARDED_ALLOW_IPS"] == ""


def test_launcher_rejects_missing_ui_and_bad_port(tmp_path, monkeypatch):
    launcher = module(ROOT / "local_demo.py")
    monkeypatch.setattr(launcher, "__file__", str(tmp_path / "local_demo.py"))
    with pytest.raises(SystemExit) as error:
        launcher.main(["api"])
    assert error.value.code == 2
    with pytest.raises(SystemExit) as error:
        launcher.main(["api", "--port", "0"])
    assert error.value.code == 2

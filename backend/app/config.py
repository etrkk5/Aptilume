import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = Path(os.getenv("REFERENCE_DIR", str(ROOT / "data")))


@dataclass
class Settings:
    data_dir: Path
    control_url: str
    secret_key: str | None = None
    allowed_hosts: str = ""
    demo: bool = True

    @classmethod
    def from_env(cls):
        path = Path(os.getenv("DATA_DIR", str(ROOT / "runtime"))).resolve()
        return cls(
            path,
            os.getenv("CONTROL_STORE_URL", f"sqlite:///{path / 'control.db'}"),
            os.getenv("SECRET_ENCRYPTION_KEY"),
            os.getenv("OUTBOUND_ALLOWED_HOSTS", ""),
            os.getenv("APP_MODE", "development") != "production",
        )

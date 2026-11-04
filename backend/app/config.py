import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
REFERENCE_DIR = Path(os.getenv("REFERENCE_DIR", str(ROOT / "data")))


@dataclass
class Settings:
    data_dir: Path
    control_url: str
    secret_key: str | None = None
    allowed_hosts: str = ""
    demo: bool = True
    public_base_url: str = ""
    allowed_db_hosts: str = ""
    allowed_directory_hosts: str = ""
    allowed_cidrs: str = ""
    llm_ca_file: str = ""
    export_retention_days: int = 7
    audit_retention_days: int = 90

    def __post_init__(self):
        self.data_dir = Path(self.data_dir).resolve()
        if (
            not 1 <= self.export_retention_days <= 90
            or not 7 <= self.audit_retention_days <= 365
        ):
            raise RuntimeError("Veri saklama süresi geçersiz.")

    def validate_web(self):
        if self.demo:
            return
        parsed = urlsplit(self.public_base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
        ):
            raise RuntimeError("Üretimde HTTPS PUBLIC_BASE_URL kök adresi gerekli.")
        self.public_base_url = self.public_base_url.rstrip("/")

    @classmethod
    def from_env(cls):
        mode = os.getenv("APP_MODE", "production")
        if mode not in {"production", "development", "test"}:
            raise RuntimeError("APP_MODE production, development veya test olmalı.")
        path = Path(os.getenv("DATA_DIR", str(ROOT / "runtime"))).resolve()
        return cls(
            path,
            os.getenv("CONTROL_STORE_URL", f"sqlite:///{path / 'control.db'}"),
            os.getenv("SECRET_ENCRYPTION_KEY"),
            os.getenv("OUTBOUND_ALLOWED_HOSTS", ""),
            mode != "production",
            os.getenv("PUBLIC_BASE_URL", ""),
            os.getenv("DB_ALLOWED_HOSTS", ""),
            os.getenv("DIRECTORY_ALLOWED_HOSTS", ""),
            os.getenv("OUTBOUND_ALLOWED_CIDRS", ""),
            os.getenv("LLM_CA_FILE", ""),
            int(os.getenv("EXPORT_RETENTION_DAYS", "7")),
            int(os.getenv("AUDIT_RETENTION_DAYS", "90")),
        )

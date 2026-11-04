"""Worker housekeeping for transient artifacts and security metadata."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from sqlalchemy import delete, select, update
from .models import (
    AuthSession,
    LoginAttempt,
    RateBucket,
    SecurityEvent,
    Export,
    DirectoryChange,
)
from .store import DomainError


def cleanup(store):
    stamp = time.time()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=store.settings.audit_retention_days)).isoformat()
    with store.cs() as s:
        s.execute(delete(AuthSession).where(AuthSession.expires_at < stamp))
        s.execute(delete(LoginAttempt).where(LoginAttempt.created_at < stamp - 900))
        s.execute(delete(RateBucket).where(RateBucket.expires_at < stamp - 900))
        s.execute(delete(SecurityEvent).where(SecurityEvent.created_at < cutoff))
        s.execute(
            delete(DirectoryChange).where(
                DirectoryChange.created_at < cutoff, DirectoryChange.status != "pending"
            )
        )
    export_cutoff = (
        now - timedelta(days=store.settings.export_retention_days)
    ).isoformat()
    with store.session() as s:
        for artifact in s.scalars(
            select(Export).where(
                Export.created_at < export_cutoff,
                Export.status.in_(["ready", "failed"]),
            )
        ):
            if artifact.file:
                candidate = Path(artifact.file)
                directory = store.settings.data_dir / "exports"
                if (
                    candidate.name == artifact.id + ".xlsx"
                    and candidate.parent.resolve() == directory.resolve()
                    and not candidate.is_symlink()
                    and directory.resolve().is_relative_to(store.settings.data_dir)
                ):
                    candidate.unlink(missing_ok=True)
            artifact.status = "expired"
            artifact.file = None

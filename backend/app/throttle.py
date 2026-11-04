"""Fixed-window limits are reserved atomically in the shared control database."""

import hashlib
import time
from sqlalchemy import update, delete
from .models import RateBucket
from .store import DomainError


def bucket_key(category, subject, window, stamp):
    digest = hashlib.sha256(str(subject).encode()).hexdigest()
    return f"{category}:{digest}:{int(stamp//window)}"


def reserve(store, category, subject, limit, window, stamp=None):
    stamp = time.time() if stamp is None else stamp
    key = bucket_key(category, subject, window, stamp)
    engine = store.control.dialect.name
    if engine == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    elif engine == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        raise RuntimeError("Unsupported control-store driver for atomic rate limits")
    statement = insert(RateBucket).values(
        key=key, count=1, expires_at=(int(stamp // window) + 1) * window
    )
    statement = statement.on_conflict_do_update(
        index_elements=[RateBucket.key],
        set_={"count": RateBucket.count + 1},
        where=RateBucket.count < limit,
    ).returning(RateBucket.key)
    with store.cs() as s:
        if s.scalar(statement) is None:
            raise DomainError(
                "rate_limited",
                "İşlem sınırına ulaşıldı. Bir süre sonra tekrar deneyin.",
                429,
            )
    return key


def refund(store, key):
    with store.cs() as s:
        s.execute(
            update(RateBucket)
            .where(RateBucket.key == key, RateBucket.count > 0)
            .values(count=RateBucket.count - 1)
        )

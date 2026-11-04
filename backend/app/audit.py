"""No request bodies, credentials, cookies, answers or raw exceptions in security logs."""

import json
import logging
import threading
import time
from sqlalchemy.exc import SQLAlchemyError
from contextvars import ContextVar
from .models import SecurityEvent

correlation_context = ContextVar("security_correlation", default="")
logger = logging.getLogger("aptilume.security")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False
_sample_lock = threading.Lock()
_sample_window = 0
_sample_count = 0
_sample_suppressed = 0

ALLOWED = {
    "reason",
    "target_id",
    "kind",
    "version",
    "count",
    "method",
    "account_hash",
    "change_id",
    "status",
}


def record(store, event, outcome="success", actor_id="", **detail):
    global _sample_window, _sample_count, _sample_suppressed
    if not actor_id and outcome == "denied":
        with _sample_lock:
            minute = int(time.time() // 60)
            if minute != _sample_window:
                if _sample_suppressed:
                    logger.warning(
                        json.dumps(
                            {
                                "event": "anonymous_denials_suppressed",
                                "count": _sample_suppressed,
                            }
                        )
                    )
                _sample_window, _sample_count, _sample_suppressed = minute, 0, 0
            if _sample_count >= 50:
                _sample_suppressed += 1
                return
            _sample_count += 1
    safe = {
        key: str(value).replace("\n", " ").replace("\r", " ")[:180]
        for key, value in detail.items()
        if key in ALLOWED
    }
    item = SecurityEvent(
        event=event,
        actor_id=actor_id,
        correlation_id=correlation_context.get(),
        outcome=outcome,
        detail=safe,
    )
    try:
        with store.cs() as s:
            s.add(item)
            s.flush()
    except SQLAlchemyError:
        logger.error(
            json.dumps(
                {
                    "event": "audit_store_unavailable",
                    "outcome": "error",
                    "correlation_id": correlation_context.get(),
                }
            )
        )
    logger.info(
        json.dumps(
            {
                "event": event,
                "actor_id": actor_id,
                "correlation_id": item.correlation_id,
                "outcome": outcome,
                "detail": safe,
            },
            ensure_ascii=False,
        )
    )

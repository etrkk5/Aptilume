"""HR-owned immutable instruction versions, pinned when background jobs are queued."""

import json
from typing import Annotated
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from .config import REFERENCE_DIR
from .models import PromptPolicy, Setting, ControlEvent, uid
from .access import require_hr
from .store import DomainError

DEFAULT_POLICY_ID = "default-v1"


def default_instructions():
    return json.loads((REFERENCE_DIR / "default-instructions.json").read_text())[
        "instructions"
    ]


def ensure_default_policy(store):
    try:
        with store.cs() as s:
            if not s.get(PromptPolicy, DEFAULT_POLICY_ID):
                s.add(
                    PromptPolicy(
                        id=DEFAULT_POLICY_ID,
                        version=1,
                        instructions=default_instructions(),
                        created_by="system",
                    )
                )
            if not s.get(Setting, "prompt_policy_active"):
                s.add(
                    Setting(
                        key="prompt_policy_active",
                        value={"id": DEFAULT_POLICY_ID, "version": 1},
                    )
                )
    except IntegrityError:
        # A concurrently starting bootstrap/API may have initialized the same rows.
        with store.cs() as s:
            if not s.get(PromptPolicy, DEFAULT_POLICY_ID) or not s.get(
                Setting, "prompt_policy_active"
            ):
                raise


def policy_data(row):
    return {
        "id": row.id,
        "version": row.version,
        "instructions": row.instructions,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


def policy(store, policy_id=None):
    with store.cs() as s:
        if policy_id is None:
            policy_id = s.get(Setting, "prompt_policy_active").value["id"]
        row = s.get(PromptPolicy, policy_id)
        if not row:
            raise DomainError(
                "policy_not_found", "Ölçüm politikası sürümü bulunamadı.", 409
            )
        return policy_data(row)


Instruction = Annotated[str, Field(min_length=30, max_length=5000)]


class Instructions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questions: Instruction
    grade: Instruction
    insights: Instruction


class PolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)
    instructions: Instructions


def install_policy_routes(app, store):
    @app.get("/api/v1/prompt-policies")
    def policies():
        require_hr()
        with store.cs() as s:
            current = s.get(Setting, "prompt_policy_active").value
            history = [
                {
                    "id": p.id,
                    "version": p.version,
                    "created_at": p.created_at,
                    "created_by": p.created_by,
                }
                for p in s.scalars(
                    select(PromptPolicy)
                    .order_by(PromptPolicy.version.desc())
                    .limit(100)
                )
            ]
        return {
            "active": policy(store, current["id"]),
            "history": history,
            "defaults": default_instructions(),
        }

    @app.get("/api/v1/prompt-policies/{policy_id}")
    def version(policy_id: str):
        require_hr()
        return policy(store, policy_id)

    @app.post("/api/v1/prompt-policies", status_code=201)
    def save(value: PolicyInput):
        actor = require_hr()
        from .throttle import reserve

        reserve(store, "policy-save", actor.id, 20, 3600)
        reserve(store, "policy-save-global", "all", 100, 3600)
        version = value.expected_version + 1
        policy_id = uid()
        with store.cs() as s:
            changed = s.execute(
                update(Setting)
                .where(
                    Setting.key == "prompt_policy_active",
                    Setting.value["version"].as_integer() == value.expected_version,
                )
                .values(value={"id": policy_id, "version": version})
            )
            if changed.rowcount != 1:
                raise DomainError(
                    "policy_conflict",
                    "Politika başka bir İK kullanıcısı tarafından değiştirildi. Güncel sürümü yükleyin.",
                    409,
                )
            instructions = value.instructions.model_dump()
            if any(len(text.strip()) < 30 for text in instructions.values()):
                raise DomainError(
                    "invalid_policy", "Her talimat en az 30 anlamlı karakter içermeli."
                )
            s.add(
                PromptPolicy(
                    id=policy_id,
                    version=version,
                    instructions=instructions,
                    created_by=actor.id,
                )
            )
            s.add(
                ControlEvent(
                    profile_id=policy_id,
                    action="prompt_policy_saved",
                    detail={"version": version, "actor_id": actor.id},
                )
            )
        from .audit import record

        record(
            store,
            "prompt_policy_saved",
            actor_id=actor.id,
            target_id=policy_id,
            version=version,
        )
        return policy(store, policy_id)

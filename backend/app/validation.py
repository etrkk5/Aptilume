from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from .store import DomainError


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    provider: Literal["mock", "openai_responses", "openai_compatible_chat"]
    model: str = Field(min_length=1, max_length=160)
    endpoint: str = Field(default="mock://apt-lab", max_length=2048)
    timeout: int = Field(default=90, ge=1, le=180)
    concurrency: int = Field(default=3, ge=1, le=20)
    scenario: Literal[
        "success",
        "timeout",
        "rate_limit",
        "unauthorized",
        "server_error",
        "invalid_json",
        "unsupported_quote",
    ] = "success"


class SQLiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    engine: Literal["sqlite"]
    path: str = Field(default="", max_length=4096)


class PostgresConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    engine: Literal["postgresql"]
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    username: str = Field(min_length=1, max_length=128)
    sslmode: Literal[
        "disable", "allow", "prefer", "require", "verify-ca", "verify-full"
    ] = "verify-full"
    sslrootcert: str = Field(default="", max_length=4096)
    timeout: int = Field(default=10, ge=1, le=30)


def connection_config(kind, value):
    try:
        model = (
            LLMConfig
            if kind == "llm"
            else SQLiteConfig if value.get("engine") == "sqlite" else PostgresConfig
        )
        return model.model_validate(value).model_dump()
    except (ValidationError, AttributeError, TypeError):
        raise DomainError(
            "invalid_connection",
            "Bağlantı alanları, sayısal sınırlar veya desteklenen seçenekler geçersiz.",
        )


class TargetInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    skill_id: str = Field(min_length=1, max_length=64)
    target_level: int = Field(ge=1, le=5)
    criticality: int = Field(ge=1, le=5)
    applicable: bool = True


class TeamContext(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    purpose: str = Field(default="", max_length=4000)
    tasks: list[str] = Field(default_factory=list, max_length=30)
    tools: list[str] = Field(default_factory=list, max_length=30)
    constraints: str = Field(default="", max_length=4000)


class TeamInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    name: str = Field(min_length=1, max_length=150)
    role: str = Field(min_length=1, max_length=200)
    context: TeamContext = Field(default_factory=TeamContext)
    targets: list[TargetInput] = Field(default_factory=list, max_length=200)


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    team_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    job_band: Literal["L1_L2", "L3_L4", "L5_L6"] = "L3_L4"
    targets: list[TargetInput] = Field(default_factory=list, max_length=200)


class PersonInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    name: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    role_profile_id: str = Field(min_length=1, max_length=64)
    job_band: Literal["L1_L2", "L3_L4", "L5_L6"] = "L3_L4"


class BindingInput(BaseModel):
    profile_id: str = Field(min_length=1, max_length=64)


class ActivateInput(BaseModel):
    copy_existing: bool = True


class ExportFilters(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    team_id: str | None = Field(default=None, max_length=64)
    skill_id: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=200)
    job_band: str | None = Field(default=None, max_length=32)
    section: Literal["common", "role"] | None = None
    response_status: Literal["not_started", "draft", "submitted"] | None = None


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    publication_id: str = Field(min_length=1, max_length=64)
    detail: bool = False
    filters: ExportFilters = Field(default_factory=ExportFilters)


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(default="", max_length=200)
    level: int = Field(ge=1, le=3)
    indicator_id: str = Field(min_length=1, max_length=100)
    weight: int = Field(ge=1, le=10)
    max_points: Literal[4] = 4
    descriptor: str = Field(min_length=1, max_length=4000)
    anchors: dict[str, str] = Field(default_factory=dict, max_length=5)


class QuestionOption(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    id: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=4000)
    correct: bool = False
    level: int | None = Field(default=None, ge=1, le=5)


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    skill_id: str = Field(min_length=1, max_length=64)
    type: Literal["open_text", "single_choice", "self_assessment"]
    prompt: str = Field(min_length=1, max_length=8000)
    section: str = Field(default="role", max_length=40)
    rubric: list[RubricCriterion] = Field(default_factory=list, max_length=5)
    options: list[QuestionOption] = Field(default_factory=list, max_length=6)
    reference: str = Field(default="", max_length=8000)
    evidence_type: Literal["scenario_reasoning", "self_reported_experience"] = (
        "scenario_reasoning"
    )


class QuestionSet(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    questions: list[GeneratedQuestion] = Field(min_length=22, max_length=22)

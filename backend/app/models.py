from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class ControlBase(DeclarativeBase):
    pass


class Profile(ControlBase):
    __tablename__ = "connection_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(12))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    config: Mapped[dict] = mapped_column(JSON)
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=now)


class ProfileVersion(ControlBase):
    __tablename__ = "connection_versions"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int]
    config: Mapped[dict] = mapped_column(JSON)
    secret: Mapped[str | None] = mapped_column(Text, nullable=True)


class Binding(ControlBase):
    __tablename__ = "service_bindings"
    purpose: Mapped[str] = mapped_column(String(40), primary_key=True)
    version_id: Mapped[str] = mapped_column(String(80))


class ControlEvent(ControlBase):
    __tablename__ = "control_events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    profile_id: Mapped[str]
    action: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


class Setting(ControlBase):
    __tablename__ = "workspace_settings"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class DirectoryUser(ControlBase):
    __tablename__ = "directory_users"
    id: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    dn: Mapped[str] = mapped_column(default="", index=True)
    manager_dn: Mapped[str] = mapped_column(default="", index=True)
    display_name: Mapped[str]
    email: Mapped[str] = mapped_column(default="")
    roles: Mapped[list] = mapped_column(JSON, default=list)
    groups: Mapped[list] = mapped_column(JSON, default=list)
    participant_id: Mapped[str | None] = mapped_column(nullable=True, index=True)
    active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(default="ldap")
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    temporary_password: Mapped[bool] = mapped_column(default=False)
    last_synced: Mapped[float] = mapped_column(default=0.0)


class AuthSession(ControlBase):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("directory_users.id"), index=True)
    csrf_token: Mapped[str]
    expires_at: Mapped[float]
    last_seen: Mapped[float]


class LoginAttempt(ControlBase):
    __tablename__ = "login_attempts"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    key: Mapped[str] = mapped_column(index=True)
    created_at: Mapped[float] = mapped_column(index=True)


class DevelopmentAction(Base):
    __tablename__ = "development_actions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    publication_id: Mapped[str | None] = mapped_column(
        ForeignKey("result_publications.id"), nullable=True
    )
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    participant_id: Mapped[str | None] = mapped_column(
        ForeignKey("participants.id"), nullable=True
    )
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.id"), nullable=True)
    title: Mapped[str]
    owner_name: Mapped[str]
    due_date: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(default="planned")
    notes: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[str]
    row_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str] = mapped_column(default=now)
    updated_at: Mapped[str] = mapped_column(default=now)


class ExportScope(Base):
    __tablename__ = "export_scopes"
    export_id: Mapped[str] = mapped_column(
        ForeignKey("export_jobs.id"), primary_key=True
    )
    creator_id: Mapped[str] = mapped_column(index=True)
    participant_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[int] = mapped_column(unique=True)
    name: Mapped[str]
    definition: Mapped[str] = mapped_column(Text)
    levels: Mapped[list] = mapped_column(JSON)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    role: Mapped[str]
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    targets: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(default=1)


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    title: Mapped[str]
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    job_band: Mapped[str] = mapped_column(default="L3_L4")


class RoleProfile(Base):
    __tablename__ = "role_profiles"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    title: Mapped[str]
    job_band: Mapped[str] = mapped_column(default="L3_L4")
    targets: Mapped[list] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
    is_default: Mapped[bool] = mapped_column(default=False)


class ParticipantRole(Base):
    __tablename__ = "participant_roles"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id"), primary_key=True
    )
    role_profile_id: Mapped[str] = mapped_column(ForeignKey("role_profiles.id"))


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    name: Mapped[str]
    status: Mapped[str] = mapped_column(default="draft", index=True)
    created_at: Mapped[str] = mapped_column(default=now)
    closed_at: Mapped[str | None] = mapped_column(nullable=True)
    publication_id: Mapped[str | None] = mapped_column(nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    row_version: Mapped[int] = mapped_column(default=1)


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("campaign_id", "participant_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id"))
    status: Mapped[str] = mapped_column(default="not_started")
    profile_snapshot: Mapped[dict] = mapped_column(JSON)
    submitted_at: Mapped[str | None] = mapped_column(nullable=True)


class Question(Base):
    __tablename__ = "question_versions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    form_key: Mapped[str]
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    type: Mapped[str]
    prompt: Mapped[str] = mapped_column(Text)
    section: Mapped[str]
    position: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    options: Mapped[list] = mapped_column(JSON, default=list)
    rubric: Mapped[list] = mapped_column(JSON, default=list)
    reference: Mapped[str] = mapped_column(Text, default="")


class AssignedQuestion(Base):
    __tablename__ = "assignment_questions"
    __table_args__ = (UniqueConstraint("assignment_id", "question_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"))
    position: Mapped[int]


class Answer(Base):
    __tablename__ = "response_revisions"
    __table_args__ = (UniqueConstraint("assignment_id", "question_id", "revision"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("question_versions.id"))
    revision: Mapped[int]
    text: Mapped[str] = mapped_column(Text, default="")
    selected: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(default="answered")
    saved_at: Mapped[str] = mapped_column(default=now)


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    assignment_id: Mapped[str] = mapped_column(
        ForeignKey("assignments.id"), unique=True
    )
    answer_ids: Mapped[list] = mapped_column(JSON)
    submitted_at: Mapped[str] = mapped_column(default=now)


class Run(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), index=True)
    status: Mapped[str] = mapped_column(default="queued")
    input_hash: Mapped[str]
    input_manifest: Mapped[list] = mapped_column(JSON)
    profile_version: Mapped[str]
    insight_profile_version: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)
    finished_at: Mapped[str | None] = mapped_column(nullable=True)
    prompt_version: Mapped[str] = mapped_column(default="evaluator-v1")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    insights: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("evaluation_runs.id"), nullable=True, index=True
    )
    kind: Mapped[str]
    dedupe_key: Mapped[str] = mapped_column(unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    lease_owner: Mapped[str | None] = mapped_column(nullable=True)
    lease_until: Mapped[float] = mapped_column(default=0.0)
    available_at: Mapped[float] = mapped_column(default=0.0)
    heartbeat_at: Mapped[str | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)


class Evaluation(Base):
    __tablename__ = "answer_evaluations"
    __table_args__ = (UniqueConstraint("run_id", "answer_id", "pass_no"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    answer_id: Mapped[str] = mapped_column(ForeignKey("response_revisions.id"))
    pass_no: Mapped[int] = mapped_column(default=1)
    status: Mapped[str]
    score: Mapped[float | None] = mapped_column(nullable=True)
    criteria: Mapped[list] = mapped_column(JSON)
    flags: Mapped[list] = mapped_column(JSON, default=list)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(default="clear")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    evaluation_id: Mapped[str] = mapped_column(
        ForeignKey("answer_evaluations.id"), index=True
    )
    score: Mapped[float | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(default="Demo içerik sorumlusu")
    created_at: Mapped[str] = mapped_column(default=now)


class Publication(Base):
    __tablename__ = "result_publications"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("evaluation_runs.id"), unique=True)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    version: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)
    published_at: Mapped[str] = mapped_column(default=now)


class Export(Base):
    __tablename__ = "export_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    publication_id: Mapped[str] = mapped_column(ForeignKey("result_publications.id"))
    filters: Mapped[dict] = mapped_column(JSON)
    detail: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(default="queued")
    file: Mapped[str | None] = mapped_column(nullable=True)
    sha256: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(default=now)


class Call(Base):
    __tablename__ = "llm_calls"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    job_id: Mapped[str] = mapped_column(index=True)
    profile_version: Mapped[str]
    model: Mapped[str]
    latency_ms: Mapped[float]
    usage: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(default=now)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    action: Mapped[str]
    entity_id: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)

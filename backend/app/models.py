import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Boolean,
    Numeric,
    Integer,
    ForeignKey,
    UniqueConstraint,
    DateTime,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(timezone.utc)


class Event(Base):
    __tablename__ = "event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String)
    submission_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submission_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blind_judging: Mapped[bool] = mapped_column(Boolean, default=True)
    fixture_sentinel: Mapped[str] = mapped_column(String, unique=True, nullable=True)


class Track(Base):
    __tablename__ = "track"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    name: Mapped[str] = mapped_column(String)


class User(Base):
    __tablename__ = "user"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)  # participant | judge | organizer | admin
    display_name: Mapped[str] = mapped_column(String)


class Team(Base):
    __tablename__ = "team"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    name: Mapped[str] = mapped_column(String)


class TeamMember(Base):
    __tablename__ = "team_member"
    team_id: Mapped[str] = mapped_column(ForeignKey("team.id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user.id"), primary_key=True)


class Invitation(Base):
    __tablename__ = "invitation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("team.id"))
    token: Mapped[str] = mapped_column(String, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Base):
    __tablename__ = "project"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    team_id: Mapped[str] = mapped_column(ForeignKey("team.id"))
    track_id: Mapped[str] = mapped_column(ForeignKey("track.id"), nullable=True)
    title: Mapped[str] = mapped_column(String)
    tagline: Mapped[str] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    repo_url: Mapped[str] = mapped_column(String, nullable=True)
    demo_url: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | submitted
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectMedia(Base):
    __tablename__ = "project_media"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"))
    kind: Mapped[str] = mapped_column(String)  # image | video
    url: Mapped[str] = mapped_column(String)


class RubricCriterion(Base):
    __tablename__ = "rubric_criterion"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    name: Mapped[str] = mapped_column(String)
    weight: Mapped[float] = mapped_column(Numeric)
    max_score: Mapped[int] = mapped_column(Integer, default=5)


class Assignment(Base):
    __tablename__ = "assignment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    judge_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"))

    __table_args__ = (UniqueConstraint("judge_id", "project_id", name="uq_assignment"),)


class ScoreDraft(Base):
    __tablename__ = "score_draft"
    judge_id: Mapped[str] = mapped_column(ForeignKey("user.id"), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"), primary_key=True)
    criterion_id: Mapped[str] = mapped_column(ForeignKey("rubric_criterion.id"), primary_key=True)
    value: Mapped[float] = mapped_column(Numeric, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Score(Base):
    __tablename__ = "score"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    judge_id: Mapped[str] = mapped_column(ForeignKey("user.id"))
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"))
    criterion_id: Mapped[str] = mapped_column(ForeignKey("rubric_criterion.id"))
    value: Mapped[float] = mapped_column(Numeric)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (
        UniqueConstraint("judge_id", "project_id", "criterion_id", name="uq_score"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    # Strictly ordered, monotonically-increasing sequence number. This --
    # not created_at, and not the (unordered) uuid `id` -- is the sole
    # basis for "what is the previous event in the chain". Timestamps
    # are not fine-grained or monotonic enough to be a reliable total
    # order under concurrent writers (two transactions can commit with
    # the same or out-of-order created_at), which previously let
    # concurrent submissions fork the chain. seq is assigned by
    # record_audit_event() under a row lock on AuditChainHead, never by
    # a database autoincrement default, so it stays correct on both
    # Postgres and the sqlite used in tests.
    seq: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"), nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String)
    prev_hash: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditChainHead(Base):
    """
    Singleton row (id is always 1) that record_audit_event() locks with
    SELECT ... FOR UPDATE before reading "what's the last event" and
    inserting the next one. Locking a single, always-present row --
    rather than locking (or racing to read) the current last AuditEvent
    row, which may not exist yet on the very first insert -- means
    every appender, including the first ever, serializes on the same
    lock and the chain cannot fork. Created once at startup by
    entrypoint.py, immediately after Base.metadata.create_all.
    """
    __tablename__ = "audit_chain_head"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    last_hash: Mapped[str] = mapped_column(String, nullable=True)


class NormalizationRun(Base):
    __tablename__ = "normalization_run"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    algorithm: Mapped[str] = mapped_column(String)
    parameters: Mapped[dict] = mapped_column(JSON)
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)


# ---- T3-lite community voting (additive; no changes to existing tables) ----

class VotingWindow(Base):
    __tablename__ = "voting_window"
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"), primary_key=True)
    open_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    close_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Vote(Base):
    __tablename__ = "vote"
    __table_args__ = (
        UniqueConstraint("event_id", "voter_id", "project_id", name="uq_vote_event_voter_project"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    voter_id: Mapped[str] = mapped_column(ForeignKey("user.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Comment(Base):
    __tablename__ = "comment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("project.id"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("user.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class JudgeRecord(Base):
    """T4(c): HMAC-signed judge participation record (issued by an organizer)."""
    __tablename__ = "judge_record"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("event.id"))
    judge_id: Mapped[str] = mapped_column(ForeignKey("user.id"), index=True)
    judge_name: Mapped[str] = mapped_column(String)
    event_name: Mapped[str] = mapped_column(String)
    reviews_completed: Mapped[int] = mapped_column(Integer)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Anchor into the tamper-evident audit chain: seq and payload_hash of the
    # `judge_record.issued` event written in the same transaction. Both are
    # covered by the HMAC signature and echoed by the public verify route.
    audit_seq: Mapped[int] = mapped_column(Integer)
    audit_hash: Mapped[str] = mapped_column(String)
    signature: Mapped[str] = mapped_column(String)

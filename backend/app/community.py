"""T3-lite community voting logic shared by the community routers."""
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config, models
from .audit import record_audit_event

VOTE_REJECT_ACTIONS = (
    "vote.duplicate_rejected",
    "vote.cap_rejected",
    "vote.window_rejected",
    "vote.own_team_rejected",
)
COMMUNITY_ACTIONS = (
    "voting_window.set",
    "vote.accepted",
    *VOTE_REJECT_ACTIONS,
    "vote.rate_limited",
    "comment.created",
    "comment.rate_limited",
)


def single_event(db: Session) -> models.Event:
    event = db.execute(select(models.Event).order_by(models.Event.name)).scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="No event configured")
    return event


def can_view_results(user: models.User | None, state: str) -> bool:
    """THE one results-visibility rule. Organizer/admin: always. Everyone
    else (visitors, participants, judges): only once voting is CLOSED."""
    if user is not None and user.role in ("organizer", "admin"):
        return True
    return state == "CLOSED"


def assert_results_visible(user: models.User | None, state: str) -> None:
    if not can_view_results(user, state):
        raise HTTPException(
            status_code=403,
            detail="Vote results are hidden until voting closes.",
        )


def order_ballot(projects, event_id: str, user_id: str) -> list:
    """Per-voter order: sha256(BALLOT_SEED + event_id + user_id + project_id).
    Server-computed only; stable per voter, different across voters."""
    def key(p):
        return hashlib.sha256(
            (config.BALLOT_SEED + event_id + user_id + p.id).encode("utf-8")
        ).hexdigest()
    return sorted(projects, key=key)


def recent_count(db: Session, model, user_col, user_id: str, *extra) -> int:
    """Rolling-limit helper: how many rows this user created recently."""
    since = datetime.now(timezone.utc) - timedelta(seconds=config.COMMUNITY_RATE_WINDOW_SECONDS)
    stmt = (
        select(func.count())
        .select_from(model)
        .where(user_col == user_id, model.created_at >= since, *extra)
    )
    return db.execute(stmt).scalar_one()


def audit_and_raise(
    db: Session, *, event_id: str, actor_id: str, action: str,
    status: int, detail: str, entity_type: str = "vote",
    entity_id: str | None = None, payload: dict | None = None,
):
    """Rejected attempts are audited: drop any open transaction, write the
    audit row in a fresh one, COMMIT, and only then raise."""
    db.rollback()
    record_audit_event(
        db, event_id=event_id, actor_id=actor_id, action=action,
        entity_type=entity_type, entity_id=entity_id, payload=payload or {},
    )
    db.commit()
    raise HTTPException(status_code=status, detail=detail)

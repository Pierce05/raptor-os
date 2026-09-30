from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import community as cm, models
from ..audit import record_audit_event
from ..database import get_db
from ..deps import require_organizer
from ..windows import voting_state, _as_utc_aware

router = APIRouter(prefix="/api/organizer/community", tags=["community-organizer"])


class WindowIn(BaseModel):
    open_at: datetime
    close_at: datetime


@router.put("/window", summary="Set the community voting window (audited)")
def set_window(body: WindowIn, user: models.User = Depends(require_organizer), db: Session = Depends(get_db)):
    open_at, close_at = _as_utc_aware(body.open_at), _as_utc_aware(body.close_at)
    open_at, close_at = open_at.astimezone(timezone.utc), close_at.astimezone(timezone.utc)
    if close_at <= open_at:
        raise HTTPException(status_code=422, detail="close_at must be after open_at")
    event = cm.single_event(db)
    w = db.get(models.VotingWindow, event.id)
    before = None
    if w is None:
        db.add(models.VotingWindow(event_id=event.id, open_at=open_at, close_at=close_at))
    else:
        before = {"open_at": _as_utc_aware(w.open_at).isoformat(), "close_at": _as_utc_aware(w.close_at).isoformat()}
        w.open_at, w.close_at = open_at, close_at
    record_audit_event(
        db, event_id=event.id, actor_id=user.id, action="voting_window.set",
        entity_type="voting_window", entity_id=event.id,
        payload={"open_at": open_at.isoformat(), "close_at": close_at.isoformat(), "previous": before},
    )
    db.commit()
    state, _ = voting_state(db, event.id)
    return {"state": state, "open_at": open_at.isoformat(), "close_at": close_at.isoformat()}


@router.get("/summary", summary="Community summary incl. top projects (organizer only)")
def summary(user: models.User = Depends(require_organizer), db: Session = Depends(get_db)):
    event = cm.single_event(db)
    state, w = voting_state(db, event.id)
    total = db.execute(select(func.count()).select_from(models.Vote).where(models.Vote.event_id == event.id)).scalar_one()
    voters = db.execute(select(func.count(func.distinct(models.Vote.voter_id))).where(models.Vote.event_id == event.id)).scalar_one()
    comments = db.execute(select(func.count()).select_from(models.Comment)).scalar_one()
    top = db.execute(
        select(models.Project.id, models.Project.title, func.count(models.Vote.id).label("n"))
        .join(models.Vote, models.Vote.project_id == models.Project.id)
        .group_by(models.Project.id, models.Project.title)
        .order_by(func.count(models.Vote.id).desc(), models.Project.title)
        .limit(5)
    ).all()
    return {
        "state": state,
        "open_at": _as_utc_aware(w.open_at).isoformat() if w else None,
        "close_at": _as_utc_aware(w.close_at).isoformat() if w else None,
        "total_votes": total,
        "unique_voters": voters,
        "comment_count": comments,
        "top_projects": [{"project_id": r[0], "title": r[1], "votes": r[2]} for r in top],
    }


@router.get("/audit", summary="Recent vote/comment audit events with payloads (organizer only)")
def community_audit(user: models.User = Depends(require_organizer), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.AuditEvent, models.User.email)
        .outerjoin(models.User, models.User.id == models.AuditEvent.actor_id)
        .where(models.AuditEvent.action.in_(cm.COMMUNITY_ACTIONS))
        .order_by(models.AuditEvent.seq.desc())
        .limit(50)
    ).all()
    return {"events": [
        {"seq": e.seq, "action": e.action, "actor_email": email, "payload": e.payload,
         "created_at": _as_utc_aware(e.created_at).isoformat()}
        for e, email in rows
    ]}

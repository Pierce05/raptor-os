from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import community as cm, config, models
from ..audit import record_audit_event
from ..database import get_db
from ..deps import get_current_user, require_user
from ..windows import voting_state

router = APIRouter(prefix="/api/community", tags=["community"])


class VoteIn(BaseModel):
    project_id: str


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=config.COMMENT_MAX_LEN)

    @field_validator("body")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment must not be blank")
        return v


def _iso(dt: datetime | None):
    from ..windows import _as_utc_aware
    return _as_utc_aware(dt).isoformat() if dt else None


@router.get("/status", summary="Voting state and window (public; no vote counts)")
def status(db: Session = Depends(get_db)):
    event = cm.single_event(db)
    state, w = voting_state(db, event.id)
    return {
        "state": state,
        "open_at": _iso(w.open_at) if w else None,
        "close_at": _iso(w.close_at) if w else None,
    }


@router.get("/ballot", summary="Projects in this voter's own stable random order, plus their votes")
def ballot(user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    event = cm.single_event(db)
    projects = db.execute(
        select(models.Project).where(models.Project.status == "submitted")
    ).scalars().all()
    ordered = cm.order_ballot(projects, event.id, user.id)
    voted = db.execute(
        select(models.Vote.project_id).where(
            models.Vote.event_id == event.id, models.Vote.voter_id == user.id
        )
    ).scalars().all()
    state, _ = voting_state(db, event.id)
    return {
        "state": state,
        "projects": [
            {"id": p.id, "title": p.title, "tagline": p.tagline, "track_id": p.track_id}
            for p in ordered
        ],
        "voted_project_ids": sorted(voted),
        "vote_limit": config.VOTE_CAP_PER_VOTER,
    }


@router.post("/votes", summary="Cast a vote (window OPEN, not own team, capped, no duplicates)")
def cast_vote(body: VoteIn, user: models.User = Depends(require_user), db: Session = Depends(get_db)):
    if user.role in ("organizer", "admin"):
        raise HTTPException(status_code=403, detail="Organizers and admins cannot vote")
    event = cm.single_event(db)
    eid, pid = event.id, body.project_id

    def reject(action, status_code, detail):
        cm.audit_and_raise(
            db, event_id=eid, actor_id=user.id, action=action, status=status_code,
            detail=detail, entity_id=pid, payload={"project_id": pid},
        )

    # Rolling limit on rejected attempts (rate-limited attempts themselves
    # are audited but not counted, so the counter can drain).
    if cm.recent_count(
        db, models.AuditEvent, models.AuditEvent.actor_id, user.id,
        models.AuditEvent.action.in_(cm.VOTE_REJECT_ACTIONS),
    ) >= config.REJECTED_VOTE_RATE_LIMIT:
        reject("vote.rate_limited", 429, "Too many rejected vote attempts; slow down.")

    state, _ = voting_state(db, eid)
    if state != "OPEN":
        reject("vote.window_rejected", 403, f"Voting is not open (state: {state}).")

    project = db.get(models.Project, pid)
    if project is None or project.status != "submitted":
        raise HTTPException(status_code=404, detail="Project not found")

    own = db.execute(
        select(models.TeamMember).where(
            models.TeamMember.team_id == project.team_id,
            models.TeamMember.user_id == user.id,
        )
    ).first()
    if own is not None:
        reject("vote.own_team_rejected", 403, "You cannot vote for your own team's project.")

    # Take the audit-chain lock FIRST. It serializes concurrent voters, so
    # the cap and duplicate checks below are race-free, and the accepted
    # audit row commits atomically with the vote row.
    record_audit_event(
        db, event_id=eid, actor_id=user.id, action="vote.accepted",
        entity_type="vote", entity_id=pid, payload={"project_id": pid},
    )
    used = db.execute(
        select(func.count()).select_from(models.Vote).where(
            models.Vote.event_id == eid, models.Vote.voter_id == user.id
        )
    ).scalar_one()
    dup = db.execute(
        select(models.Vote.id).where(
            models.Vote.event_id == eid, models.Vote.voter_id == user.id,
            models.Vote.project_id == pid,
        )
    ).first()
    if dup is not None:
        reject("vote.duplicate_rejected", 409, "You already voted for this project.")
    if used >= config.VOTE_CAP_PER_VOTER:
        reject("vote.cap_rejected", 403, f"Vote limit reached ({config.VOTE_CAP_PER_VOTER}).")

    db.add(models.Vote(event_id=eid, voter_id=user.id, project_id=pid))
    try:
        db.commit()
    except IntegrityError:
        # Uniqueness backstop for a duplicate race: roll back, then audit
        # in a fresh transaction.
        reject("vote.duplicate_rejected", 409, "You already voted for this project.")

    voted = db.execute(
        select(models.Vote.project_id).where(
            models.Vote.event_id == eid, models.Vote.voter_id == user.id
        )
    ).scalars().all()
    return {"ok": True, "voted_project_ids": sorted(voted)}


@router.get("/results", summary="Vote totals (organizer/admin always; everyone else only after CLOSED)")
def results(user: models.User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    event = cm.single_event(db)
    state, _ = voting_state(db, event.id)
    cm.assert_results_visible(user, state)
    rows = db.execute(
        select(models.Project.id, models.Project.title, func.count(models.Vote.id))
        .select_from(models.Project)
        .outerjoin(models.Vote, models.Vote.project_id == models.Project.id)
        .where(models.Project.status == "submitted")
        .group_by(models.Project.id, models.Project.title)
    ).all()
    out = [{"project_id": r[0], "title": r[1], "votes": r[2]} for r in rows]
    out.sort(key=lambda x: (-x["votes"], x["title"]))
    return {"state": state, "results": out}


def _comment_out(c: models.Comment, author: str):
    return {"id": c.id, "body": c.body, "author": author, "created_at": _iso(c.created_at)}


@router.get("/projects/{project_id}/comments", summary="List comments on a project (public)")
def list_comments(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if project is None or project.status != "submitted":
        raise HTTPException(status_code=404, detail="Not found")
    rows = db.execute(
        select(models.Comment, models.User.display_name)
        .join(models.User, models.User.id == models.Comment.author_id)
        .where(models.Comment.project_id == project_id)
        .order_by(models.Comment.created_at.asc())
    ).all()
    return [_comment_out(c, name) for c, name in rows]


@router.post("/projects/{project_id}/comments", summary="Post a comment (1-500 chars, rate limited)")
def post_comment(
    project_id: str, body: CommentIn,
    user: models.User = Depends(require_user), db: Session = Depends(get_db),
):
    project = db.get(models.Project, project_id)
    if project is None or project.status != "submitted":
        raise HTTPException(status_code=404, detail="Not found")
    event = cm.single_event(db)
    if cm.recent_count(
        db, models.Comment, models.Comment.author_id, user.id
    ) >= config.COMMENT_RATE_LIMIT:
        cm.audit_and_raise(
            db, event_id=event.id, actor_id=user.id, action="comment.rate_limited",
            status=429, detail="Too many comments; slow down.",
            entity_type="comment", entity_id=project_id, payload={"project_id": project_id},
        )
    # Audit first: record_audit_event takes the chain lock (BEGIN IMMEDIATE on
    # SQLite), which must happen before any flushed write in this transaction.
    comment_id = models.new_id()
    record_audit_event(
        db, event_id=event.id, actor_id=user.id, action="comment.created",
        entity_type="comment", entity_id=comment_id,
        payload={"project_id": project_id, "length": len(body.body)},
    )
    comment = models.Comment(
        id=comment_id, project_id=project_id, author_id=user.id, body=body.body
    )
    db.add(comment)
    db.commit()
    return _comment_out(comment, user.display_name)

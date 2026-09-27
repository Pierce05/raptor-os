import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_participant

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.post("")
def create_team(
    body: schemas.TeamCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    team = models.Team(event_id=body.event_id, name=body.name)
    db.add(team)
    db.flush()
    db.add(models.TeamMember(team_id=team.id, user_id=user.id))
    db.commit()
    return {"id": team.id, "name": team.name}


@router.post("/{team_id}/invite")
def invite(
    team_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    membership = db.get(models.TeamMember, (team_id, user.id))
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")
    token = secrets.token_urlsafe(16)
    invitation = models.Invitation(
        team_id=team_id,
        token=token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=3),
    )
    db.add(invitation)
    db.commit()
    return {"token": token, "expires_at": invitation.expires_at}


@router.post("/join/{token}")
def join(
    token: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    invitation = db.execute(
        select(models.Invitation).where(models.Invitation.token == token)
    ).scalar_one_or_none()
    if not invitation or invitation.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    existing = db.get(models.TeamMember, (invitation.team_id, user.id))
    if not existing:
        db.add(models.TeamMember(team_id=invitation.team_id, user_id=user.id))
        db.commit()
    return {"team_id": invitation.team_id}

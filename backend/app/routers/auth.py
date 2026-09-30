from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import verify_password
from ..deps import require_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", summary="Log in with email and password; sets the session cookie")
def login(body: schemas.LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.execute(
        select(models.User).where(models.User.email == body.email)
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    request.session["user_id"] = user.id
    return {"id": user.id, "role": user.role, "display_name": user.display_name}


@router.post("/logout", summary="Log out and clear the session")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me", response_model=schemas.MeResponse, summary="Return the logged-in user")
def me(
    user: models.User = Depends(require_user),
    db: Session = Depends(get_db),
):
    team_id = None
    team_name = None
    event_id = None

    membership = db.execute(
        select(models.TeamMember).where(
            models.TeamMember.user_id == user.id
        )
    ).scalars().first()

    if membership:
        team = db.get(models.Team, membership.team_id)

        if team:
            team_id = team.id
            team_name = team.name
            event_id = team.event_id

    # RAPTOR-OS currently runs one event per deployment.
    # Give participants without a team the active event too.
    if event_id is None:
        event = db.execute(
            select(models.Event)
        ).scalars().first()

        if event:
            event_id = event.id

    return schemas.MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        event_id=event_id,
        team_id=team_id,
        team_name=team_name,
    )
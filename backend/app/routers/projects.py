from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_participant
from ..windows import assert_submission_window_open
from ..audit import record_audit_event

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _users_team(db: Session, user_id: str) -> models.Team | None:
    membership = db.execute(
        select(models.TeamMember).where(models.TeamMember.user_id == user_id)
    ).scalar_one_or_none()
    if not membership:
        return None
    return db.get(models.Team, membership.team_id)


def _events_for_team(db: Session, team: models.Team) -> models.Event:
    return db.get(models.Event, team.event_id)


@router.get("/mine", response_model=schemas.ProjectOut | None)
def my_project(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    """
    Lets the participant dashboard restore its state on page load or
    refresh, instead of showing an empty draft form when a project
    already exists in the DB for this participant's team. Returns null
    (not 404) when no project has been created yet -- that's a normal,
    expected state, not an error.
    """
    team = _users_team(db, user.id)
    if not team:
        return None
    return db.execute(
        select(models.Project).where(models.Project.team_id == team.id)
    ).scalars().first()


@router.post("", response_model=schemas.ProjectOut)
def create_project(
    body: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    team = _users_team(db, user.id)
    if not team:
        raise HTTPException(status_code=400, detail="Join or create a team first")
    event = _events_for_team(db, team)
    assert_submission_window_open(db, event.id)

    project = models.Project(team_id=team.id, **body.model_dump())
    db.add(project)
    db.flush()
    record_audit_event(
        db,
        event_id=event.id,
        actor_id=user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        payload={"title": project.title},
    )
    db.commit()
    db.refresh(project)
    return project


@router.patch("/{project_id}", response_model=schemas.ProjectOut)
def edit_project(
    project_id: str,
    body: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Not found")
    team = db.get(models.Team, project.team_id)
    membership = db.get(models.TeamMember, (team.id, user.id))
    if not membership:
        raise HTTPException(status_code=403, detail="Not your project")
    if project.status != "draft":
        raise HTTPException(status_code=400, detail="Cannot edit a submitted project")

    event = _events_for_team(db, team)
    assert_submission_window_open(db, event.id)

    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(project, k, v)
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/submit", response_model=schemas.ProjectOut)
def submit_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_participant),
):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Not found")
    team = db.get(models.Team, project.team_id)
    membership = db.get(models.TeamMember, (team.id, user.id))
    if not membership:
        raise HTTPException(status_code=403, detail="Not your project")

    event = _events_for_team(db, team)
    assert_submission_window_open(db, event.id)

    project.status = "submitted"
    project.submitted_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        event_id=event.id,
        actor_id=user.id,
        action="project.submitted",
        entity_type="project",
        entity_id=project.id,
        payload={"title": project.title},
    )
    db.commit()
    db.refresh(project)
    return project

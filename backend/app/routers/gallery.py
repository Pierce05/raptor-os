from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/gallery", tags=["gallery"])


@router.get("", response_model=list[schemas.ProjectOut])
def list_gallery(
    db: Session = Depends(get_db),
    track_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
):
    """Public. No auth. Only SUBMITTED projects are visible."""
    stmt = select(models.Project).where(models.Project.status == "submitted")
    if track_id:
        stmt = stmt.where(models.Project.track_id == track_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(models.Project.title.ilike(like))
    projects = db.execute(stmt).scalars().all()
    return projects


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project or project.status != "submitted":
        raise HTTPException(status_code=404, detail="Not found")
    return project

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import require_judge
from ..audit import record_audit_event

router = APIRouter(prefix="/api/judge", tags=["judge"])


def _assert_assigned(db: Session, judge_id: str, project_id: str) -> models.Assignment:
    """
    The core T2 control: derive the judge's identity from the SESSION
    (require_judge -> current user), never from a path/query parameter.
    A judge who is not assigned to this project gets 403, even if they
    know the project_id.
    """
    assignment = db.execute(
        select(models.Assignment).where(
            models.Assignment.judge_id == judge_id,
            models.Assignment.project_id == project_id,
        )
    ).scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=403, detail="Not assigned to this project")
    return assignment


@router.get("/queue", summary="List the projects assigned to the calling judge")
def queue(db: Session = Depends(get_db), user: models.User = Depends(require_judge)):
    assignments = db.execute(
        select(models.Assignment).where(models.Assignment.judge_id == user.id)
    ).scalars().all()
    project_ids = [a.project_id for a in assignments]
    projects = db.execute(
        select(models.Project).where(models.Project.id.in_(project_ids))
    ).scalars().all() if project_ids else []

    scored_ids = {
        s.project_id
        for s in db.execute(
            select(models.Score).where(models.Score.judge_id == user.id)
        ).scalars().all()
    }
    return [
        {
            "project_id": p.id,
            "title": p.title,  # blind_judging redaction happens in the detail endpoint
            "scored": p.id in scored_ids,
        }
        for p in projects
    ]


@router.get("/project/{project_id}", summary="Get an assigned project for judging (identity-redacted when blind)")
def project_for_judging(
    project_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_judge),
):
    _assert_assigned(db, user.id, project_id)
    project = db.get(models.Project, project_id)
    team = db.get(models.Team, project.team_id)
    event = db.get(models.Event, team.event_id)

    payload = {
        "id": project.id,
        "title": project.title,
        "tagline": project.tagline,
        "description": project.description,
        "demo_url": project.demo_url,
        "repo_url": project.repo_url,
    }
    if event.blind_judging:
        # Backend-enforced redaction, not a frontend CSS trick. Team/member
        # identity is never included in this response. Repo/demo URLs may
        # still leak identity -- documented as a known limitation.
        payload.pop("repo_url", None)
        payload["_blind_note"] = (
            "Team identity is redacted. Repo/demo URLs are shown as-is and "
            "may reveal identifying information (documented limitation)."
        )
    else:
        payload["repo_url"] = project.repo_url

    criteria = db.execute(select(models.RubricCriterion).where(
        models.RubricCriterion.event_id == event.id
    )).scalars().all()
    payload["criteria"] = [
        {"id": c.id, "name": c.name, "max_score": c.max_score, "weight": float(c.weight)}
        for c in criteria
    ]
    return payload


@router.put("/scores/{project_id}/draft", summary="Autosave draft scores for an assigned project")
def save_draft(
    project_id: str,
    body: schemas.ScoreSubmitIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_judge),
):
    _assert_assigned(db, user.id, project_id)
    for item in body.scores:
        existing = db.get(models.ScoreDraft, (user.id, project_id, item.criterion_id))
        if existing:
            existing.value = item.value
            existing.feedback = item.feedback
        else:
            db.add(models.ScoreDraft(
                judge_id=user.id,
                project_id=project_id,
                criterion_id=item.criterion_id,
                value=item.value,
                feedback=item.feedback,
            ))
    db.commit()
    return {"ok": True}


@router.get("/scores/{project_id}", summary="Get the calling judge's own scores for one project")
def my_scores_for_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_judge),
):
    """
    Returns only the requesting judge's OWN scores. There is deliberately
    no way to pass a different judge_id -- this is what keeps Judge B
    from ever reading Judge A's scores (acceptance check #5).
    """
    _assert_assigned(db, user.id, project_id)
    scores = db.execute(
        select(models.Score).where(
            models.Score.judge_id == user.id, models.Score.project_id == project_id
        )
    ).scalars().all()
    drafts = db.execute(
        select(models.ScoreDraft).where(
            models.ScoreDraft.judge_id == user.id, models.ScoreDraft.project_id == project_id
        )
    ).scalars().all()
    return {
        "submitted": [{"criterion_id": s.criterion_id, "value": float(s.value)} for s in scores],
        "drafts": [{"criterion_id": d.criterion_id, "value": float(d.value) if d.value is not None else None} for d in drafts],
    }


@router.get("/scores", summary="Get all of the calling judge's own scores")
def my_scores(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_judge),
):
    """
    All of the requesting judge's OWN scores, across every assigned
    project -- no path/query parameter at all. Exists specifically to
    match the real DOGFOOD run.py: it does plain string concatenation
    on the [routes] value in .dogfood.toml with NO templating, so
    judge_scores cannot depend on a specific project_id being baked
    into the config -- it has to work standing alone, for whichever
    judge's session cookie is attached. Identity comes only from
    require_judge's session lookup, same guarantee as
    my_scores_for_project above.
    """
    scores = db.execute(
        select(models.Score).where(models.Score.judge_id == user.id)
    ).scalars().all()
    drafts = db.execute(
        select(models.ScoreDraft).where(models.ScoreDraft.judge_id == user.id)
    ).scalars().all()
    return {
        "submitted": [
            {"project_id": s.project_id, "criterion_id": s.criterion_id, "value": float(s.value)}
            for s in scores
        ],
        "drafts": [
            {"project_id": d.project_id, "criterion_id": d.criterion_id, "value": float(d.value) if d.value is not None else None}
            for d in drafts
        ],
    }


@router.post("/scores/{project_id}/submit", summary="Submit final, immutable scores for an assigned project")
def submit_scores(
    project_id: str,
    body: schemas.ScoreSubmitIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_judge),
):
    _assert_assigned(db, user.id, project_id)
    project = db.get(models.Project, project_id)
    team = db.get(models.Team, project.team_id)
    event_id = team.event_id

    for item in body.scores:
        existing = db.execute(
            select(models.Score).where(
                models.Score.judge_id == user.id,
                models.Score.project_id == project_id,
                models.Score.criterion_id == item.criterion_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Score already submitted (immutable)")
        if item.value is None:
            raise HTTPException(status_code=400, detail="Missing value for a criterion")
        db.add(models.Score(
            judge_id=user.id,
            project_id=project_id,
            criterion_id=item.criterion_id,
            value=item.value,
            feedback=item.feedback,
        ))

    record_audit_event(
        db,
        event_id=event_id,
        actor_id=user.id,
        action="score.submitted",
        entity_type="project",
        entity_id=project_id,
        payload={"criteria_count": len(body.scores)},
    )
    db.commit()
    return {"ok": True}

"""T4(b): event export in the fixtures.json shape.

Emits {event, tracks, judges, teams, projects, scores} so the output can be
fed straight back into seed.seed_from_file(). Ids in the output ("trk_01",
"jdg_01", ...) are positional labels generated here, never database ids, and
the ordering is fully determined by content so two exports of equivalent data
are byte-identical apart from nothing at all.

What does NOT survive a round trip is listed in DATA-MODEL.md.
"""
from datetime import timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def _num(v):
    if isinstance(v, Decimal):
        v = float(v)
    return int(v) if isinstance(v, float) and v.is_integer() else v


def _z(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:  # SQLite hands back naive UTC
        return dt.isoformat() + "Z"
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_event_export(db: Session, event: models.Event) -> dict:
    tracks = db.execute(
        select(models.Track).where(models.Track.event_id == event.id)
        .order_by(models.Track.name, models.Track.id)
    ).scalars().all()
    track_label = {t.id: f"trk_{i:02d}" for i, t in enumerate(tracks, 1)}

    team_rows = db.execute(
        select(models.Team).where(models.Team.event_id == event.id)
    ).scalars().all()
    members: dict[str, list[str]] = {t.id: [] for t in team_rows}
    for team_id, email in db.execute(
        select(models.TeamMember.team_id, models.User.email)
        .join(models.User, models.User.id == models.TeamMember.user_id)
    ).all():
        if team_id in members:
            members[team_id].append(email)
    teams = sorted(team_rows, key=lambda t: (t.name, sorted(members[t.id])))
    team_label = {t.id: f"tm_{i:02d}" for i, t in enumerate(teams, 1)}

    judges = db.execute(
        select(models.User).where(models.User.role == "judge").order_by(models.User.email)
    ).scalars().all()
    judge_label = {j.id: f"jdg_{i:02d}" for i, j in enumerate(judges, 1)}

    team_name = {t.id: t.name for t in teams}
    projects = [
        p for p in db.execute(
            select(models.Project).where(models.Project.status == "submitted")
        ).scalars().all()
        if p.team_id in team_label
    ]
    projects.sort(key=lambda p: (p.title, team_name[p.team_id], p.repo_url or "", p.id))
    project_label = {p.id: f"prj_{i:02d}" for i, p in enumerate(projects, 1)}

    criterion_name = {
        c.id: c.name for c in db.execute(
            select(models.RubricCriterion).where(models.RubricCriterion.event_id == event.id)
        ).scalars().all()
    }
    grouped: dict[tuple[str, str], dict] = {}
    for s in db.execute(select(models.Score).where(models.Score.submitted_at.is_not(None))).scalars().all():
        if s.judge_id not in judge_label or s.project_id not in project_label or s.criterion_id not in criterion_name:
            continue
        g = grouped.setdefault((s.judge_id, s.project_id), {"criteria": {}, "comment": None})
        g["criteria"][criterion_name[s.criterion_id]] = _num(s.value)
        if g["comment"] is None and s.feedback:
            g["comment"] = s.feedback
    scores = [
        {
            "judge": judge_label[j], "project": project_label[p],
            "criteria": dict(sorted(g["criteria"].items())), "comment": g["comment"] or "",
        }
        for (j, p), g in grouped.items()
    ]
    scores.sort(key=lambda s: (s["judge"], s["project"]))

    return {
        "event": {
            "id": "evt_01", "name": event.name,
            "submissions_close": _z(event.submission_closes_at),
        },
        "tracks": [{"id": track_label[t.id], "name": t.name} for t in tracks],
        "judges": [
            # Judge->track affinity is not stored by the seeder, so it cannot be exported.
            {"id": judge_label[j.id], "name": j.display_name, "email": j.email, "tracks": []}
            for j in judges
        ],
        "teams": [
            {"id": team_label[t.id], "name": t.name, "members": sorted(members[t.id])}
            for t in teams
        ],
        "projects": [
            {
                "id": project_label[p.id], "team": team_label[p.team_id],
                "track": track_label.get(p.track_id),
                "title": p.title,
                "summary": p.description or p.tagline or "",
                "repo_url": p.repo_url,
                "submitted_at": _z(p.submitted_at),
            }
            for p in projects
        ],
        "scores": scores,
    }

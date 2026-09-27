"""
Idempotent fixture loader for the REAL DOGFOOD 2026 fixtures.json shape:

    event:    {id, name, submissions_close}   -- NOT opens_at/closes_at
    tracks:   [{id, name}, ...]
    judges:   [{id, name, email, tracks: [track_id, ...]}, ...]
    teams:    [{id, name, members: [email, ...]}, ...]
    projects: [{id, team, track, title, summary, repo_url, submitted_at}]
    scores:   [{judge, project, criteria: {name: value, ...}, comment}]

This is a full rewrite, not a patch -- the previous version of this file
was written against an earlier, self-invented placeholder shape
(top-level "users"/"rubric" keys, tracks as plain strings, projects
referencing teams by name) that does not exist anywhere in the real
file. Every one of those assumptions is wrong against the real fixture
and would KeyError or silently produce empty data on contact.

Notably absent from the real fixture, and synthesized here instead:
  - No rubric. The scoring dimensions only exist implicitly as the
    union of criteria keys used across every score entry (e.g.
    "functionality", "quality", "innovation"). We collect that union
    and create one RubricCriterion per unique name, weighted equally
    (max_score=5, matching the fixture's 1-5 integer scale). This is a
    real design decision, defended in JUDGING.md: the alternative
    (guessing organizer-intended weights) has no basis in the data,
    equal weighting is the only assumption the fixture itself supports.
  - No organizer account at all, and no passwords for judges or team
    members. We synthesize exactly one organizer account, and give
    every real judge/team-member email a single shared, fixed seed
    password (SEED_PASSWORD below) -- these are fixture/test identities
    with no real credentials to begin with, not real people's accounts.
  - No explicit assignment records. A judge scoring a project implies
    they were assigned it; we create one Assignment row per unique
    (judge, project) pair that appears in `scores`, before inserting
    the Score rows themselves, so judge queues/dashboards stay
    consistent with what was actually judged. We do not fabricate
    additional assignment-only rows with no score -- the fixture's own
    uneven review counts (some projects have 2 scores, others 5) are
    already the "awkward case" data; inventing more would misrepresent
    the source file.

Test/demo account selection (documented here and mirrored in
.dogfood.toml's [seed_accounts]):
  - organizer : synthesized, not tied to any fixture entity
  - judge_a   : the fixture's first judge (judges[0]) -- happens to have
                only ONE score in the real file, which makes it a good,
                real demonstration of the sparse-judge shrinkage case
                documented in JUDGING.md, not a contrived example
  - judge_b   : the fixture's second judge (judges[1])
  - participant: the first member of the fixture's first team
                 (teams[0].members[0]) -- a real team with a real
                 submitted project, so the T1.3 deadline-rejection
                 check exercises "team exists, event is closed" rather
                 than an uninteresting "no team yet" 400
"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .security import hash_password

SEED_PASSWORD = "dogfood-seed-2026"
# The real fixture's event has no submission_opens_at at all (only
# submissions_close). Our schema requires a non-null opens_at, so we
# default to a fixed, safely-in-the-past constant -- there is no
# fixture data to derive this from, so a hardcoded default is the
# honest choice rather than guessing a relative offset.
DEFAULT_OPENS_AT = "2020-01-01T00:00:00Z"


def _sentinel_for(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]


def _parse_iso(value: str) -> datetime:
    """
    fixtures.json dates are ISO-8601 with a trailing 'Z'. datetime.fromiso
    format() only accepts '+00:00'-style offsets (pre-3.11 at least), not
    a bare 'Z', so this normalizes that before parsing. Assigning the raw
    string straight to a DateTime column happens to work on Postgres
    (implicit cast) but breaks on SQLite (AttributeError on a plain str),
    so this must always produce a real datetime regardless of backend.
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def seed_from_file(db: Session, path: str) -> None:
    with open(path, "r") as f:
        raw_text = f.read()
    data = json.loads(raw_text)
    sentinel = _sentinel_for(raw_text)

    existing = db.execute(
        select(models.Event).where(models.Event.fixture_sentinel == sentinel)
    ).scalar_one_or_none()
    if existing:
        print(f"[seed] fixtures already loaded (sentinel={sentinel}); skipping")
        return

    print(f"[seed] loading fixtures (sentinel={sentinel})")

    # --- Event ------------------------------------------------------
    ev = data["event"]
    event = models.Event(
        name=ev["name"],
        submission_opens_at=_parse_iso(DEFAULT_OPENS_AT),
        submission_closes_at=_parse_iso(ev["submissions_close"]),
        blind_judging=True,
        fixture_sentinel=sentinel,
    )
    db.add(event)
    db.flush()

    # --- Tracks (real shape: list of {id, name}) ---------------------
    track_by_id = {}
    for t in data.get("tracks", []):
        track = models.Track(event_id=event.id, name=t["name"])
        db.add(track)
        db.flush()
        track_by_id[t["id"]] = track.id

    # --- Rubric: synthesized from the union of criteria keys ---------
    criterion_names = []
    seen = set()
    for s in data.get("scores", []):
        for crit_name in s.get("criteria", {}).keys():
            if crit_name not in seen:
                seen.add(crit_name)
                criterion_names.append(crit_name)
    criterion_by_name = {}
    if criterion_names:
        equal_weight = round(1.0 / len(criterion_names), 4)
        for name in criterion_names:
            crit = models.RubricCriterion(
                event_id=event.id, name=name, weight=equal_weight, max_score=5
            )
            db.add(crit)
            db.flush()
            criterion_by_name[name] = crit.id

    # --- Judges (real shape: separate top-level array) ----------------
    judge_by_fixture_id = {}
    for j in data.get("judges", []):
        user = models.User(
            email=j["email"],
            password_hash=hash_password(SEED_PASSWORD),
            role="judge",
            display_name=j.get("name", j["email"]),
        )
        db.add(user)
        db.flush()
        judge_by_fixture_id[j["id"]] = user.id

    # --- Teams + their real members (real shape: members are raw ------
    # email strings with no account of their own until now) ------------
    team_by_fixture_id = {}
    participant_email_by_fixture_team = {}
    for t in data.get("teams", []):
        team = models.Team(event_id=event.id, name=t["name"])
        db.add(team)
        db.flush()
        team_by_fixture_id[t["id"]] = team.id
        member_emails = t.get("members", [])
        if member_emails:
            participant_email_by_fixture_team[t["id"]] = member_emails[0]
        for member_email in member_emails:
            user = models.User(
                email=member_email,
                password_hash=hash_password(SEED_PASSWORD),
                role="participant",
                display_name=member_email.split("@")[0],
            )
            db.add(user)
            db.flush()
            db.add(models.TeamMember(team_id=team.id, user_id=user.id))

    # --- Projects (real shape: team/track referenced by id) -----------
    project_by_fixture_id = {}
    for p in data.get("projects", []):
        team_id = team_by_fixture_id.get(p["team"])
        track_id = track_by_id.get(p.get("track"))
        summary = p.get("summary", "")
        project = models.Project(
            team_id=team_id,
            track_id=track_id,
            title=p["title"],
            tagline=summary,
            description=summary,
            repo_url=p.get("repo_url"),
            demo_url=None,
            status="submitted",
        )
        db.add(project)
        db.flush()
        project_by_fixture_id[p["id"]] = project.id

    # --- Scores: creates the implied Assignment, then the immutable ---
    # Score row itself. This is pre-existing, already-judged fixture ---
    # data -- seeded directly as submitted Scores, not ScoreDrafts. -----
    assignment_seen = set()
    now = datetime.now(timezone.utc)
    for s in data.get("scores", []):
        judge_id = judge_by_fixture_id.get(s["judge"])
        project_id = project_by_fixture_id.get(s["project"])
        if not judge_id or not project_id:
            continue
        pair = (judge_id, project_id)
        if pair not in assignment_seen:
            assignment_seen.add(pair)
            db.add(models.Assignment(judge_id=judge_id, project_id=project_id))
        feedback = s.get("comment") or None
        for crit_name, value in s.get("criteria", {}).items():
            criterion_id = criterion_by_name.get(crit_name)
            if not criterion_id:
                continue
            db.add(models.Score(
                judge_id=judge_id,
                project_id=project_id,
                criterion_id=criterion_id,
                value=value,
                feedback=feedback,
                submitted_at=now,
            ))

    db.flush()

    # --- Synthesized test/demo accounts, not present in the fixture ---
    db.add(models.User(
        email="organizer@raptor.local",
        password_hash=hash_password(SEED_PASSWORD),
        role="organizer",
        display_name="Organizer",
    ))

    db.commit()

    judges_list = data.get("judges", [])
    teams_list = data.get("teams", [])
    judge_a_email = judges_list[0]["email"] if len(judges_list) > 0 else None
    judge_b_email = judges_list[1]["email"] if len(judges_list) > 1 else None
    participant_email = (
        teams_list[0]["members"][0]
        if teams_list and teams_list[0].get("members")
        else None
    )
    print(
        "[seed] done -- "
        f"judges={len(judge_by_fixture_id)} teams={len(team_by_fixture_id)} "
        f"projects={len(project_by_fixture_id)} criteria={len(criterion_by_name)} "
        f"scores={len(data.get('scores', []))}"
    )
    print(
        "[seed] test accounts (all share the same seed password): "
        f"organizer=organizer@raptor.local judge_a={judge_a_email} "
        f"judge_b={judge_b_email} participant={participant_email} "
        f"password={SEED_PASSWORD!r} for all"
    )

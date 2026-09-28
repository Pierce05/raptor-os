"""T4(b): export -> fresh DB -> export again; equal by content, never by id."""
import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models, seed
from app.database import Base
from app.export import build_event_export
from tests.conftest import fresh_client, login

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures.json"


@pytest.fixture(autouse=True)
def cheap_hashing(monkeypatch):
    # bcrypt on ~130 seeded accounts is slow and irrelevant to this test.
    monkeypatch.setattr(seed, "hash_password", lambda pw: "not-a-real-hash")


def _fresh_session():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    return Session(engine), path


def _seed(db, fixture_path):
    seed.seed_from_file(db, str(fixture_path))
    return db.query(models.Event).one()


def signature(exp: dict) -> dict:
    """Structural view keyed by titles, emails and criteria; ids resolved away."""
    track = {t["id"]: t["name"] for t in exp["tracks"]}
    team = {t["id"]: t["name"] for t in exp["teams"]}
    judge = {j["id"]: j["email"] for j in exp["judges"]}
    proj = {p["id"]: p["title"] for p in exp["projects"]}
    return {
        "event": (exp["event"]["name"], exp["event"]["submissions_close"]),
        "tracks": sorted(track.values()),
        "judges": sorted((j["email"], j["name"]) for j in exp["judges"]),
        "teams": sorted((t["name"], tuple(sorted(t["members"]))) for t in exp["teams"]),
        "member_emails": sorted(e for t in exp["teams"] for e in t["members"]),
        "titles": sorted(proj.values()),
        "projects": sorted(
            (p["title"], p["summary"], p["repo_url"], team[p["team"]], track.get(p["track"]))
            for p in exp["projects"]
        ),
        "scores": sorted(
            (judge[s["judge"]], proj[s["project"]],
             tuple(sorted(s["criteria"].items())), s["comment"])
            for s in exp["scores"]
        ),
    }


def test_export_roundtrip_is_structurally_equal(db_session):
    event = _seed(db_session, FIXTURES)
    first = build_event_export(db_session, event)
    assert set(first) == {"event", "tracks", "judges", "teams", "projects", "scores"}
    assert first["scores"] and first["projects"] and first["judges"]

    # The export also matches the ORIGINAL fixture on the fields that matter.
    orig = json.loads(FIXTURES.read_text())
    o_judge = {j["id"]: j["email"] for j in orig["judges"]}
    o_proj = {p["id"]: p["title"] for p in orig["projects"]}
    assert signature(first)["titles"] == sorted(o_proj.values())
    assert signature(first)["member_emails"] == sorted(e for t in orig["teams"] for e in t["members"])
    assert signature(first)["scores"] == sorted(
        (o_judge[s["judge"]], o_proj[s["project"]], tuple(sorted(s["criteria"].items())), s["comment"])
        for s in orig["scores"]
    )

    # Load the export into a FRESH database through the existing seeder.
    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    tmp.write_text(json.dumps(first))
    fresh, _ = _fresh_session()
    try:
        second = build_event_export(fresh, _seed(fresh, tmp))
    finally:
        fresh.close()
    assert signature(second) == signature(first)


def test_export_route_is_organizer_only_and_matches_shape(db_session, tmp_path, monkeypatch):
    # Real hashing for the login round trip, on a tiny fixture.
    from app.security import hash_password
    monkeypatch.setattr(seed, "hash_password", hash_password)
    tiny = {
        "event": {"id": "e", "name": "Tiny", "submissions_close": "2026-03-01T18:00:00Z"},
        "tracks": [{"id": "t1", "name": "Tools"}],
        "judges": [{"id": "j1", "name": "Judy", "email": "judy@example.org", "tracks": []}],
        "teams": [{"id": "m1", "name": "Alpha", "members": ["a@example.org", "b@example.org"]}],
        "projects": [{"id": "p1", "team": "m1", "track": "t1", "title": "Thing",
                      "summary": "S", "repo_url": "https://example.org/r", "submitted_at": None}],
        "scores": [{"judge": "j1", "project": "p1", "criteria": {"quality": 4, "innovation": 2}, "comment": "ok"}],
    }
    f = tmp_path / "tiny.json"
    f.write_text(json.dumps(tiny))
    seed.seed_from_file(db_session, str(f))

    assert fresh_client().get("/api/organizer/export/event.json").status_code == 401
    part = fresh_client()
    login(part, "a@example.org", seed.SEED_PASSWORD)
    assert part.get("/api/organizer/export/event.json").status_code == 403
    org = fresh_client()
    login(org, "organizer@raptor.local", seed.SEED_PASSWORD)
    body = org.get("/api/organizer/export/event.json").json()
    assert body["teams"][0]["members"] == ["a@example.org", "b@example.org"]
    assert body["scores"][0]["criteria"] == {"innovation": 2, "quality": 4}
    assert body["scores"][0]["comment"] == "ok"
    assert "organizer@raptor.local" not in json.dumps(body)
    assert "password" not in json.dumps(body).lower()

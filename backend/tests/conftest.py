"""
Test fixtures for the backend test suite.

Points DATABASE_URL at a throwaway sqlite file BEFORE importing anything
under app.*, since app.config reads the env var at import time. A file
(not sqlite:///:memory:) is used because SQLAlchemy's default engine
opens a fresh connection per Session, and an in-memory sqlite db is
per-connection -- a file is what lets the test's setup session and the
app's request-scoped `get_db()` sessions see the same committed data.
"""
import os
import tempfile
from datetime import datetime, timezone

_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db_path}"
os.environ["SEED_ON_START"] = "false"
os.environ.setdefault("SESSION_SECRET", "test-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app import models, audit  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    # app.main.ensure_audit_chain_head() only runs once, at module
    # import time -- but this fixture just dropped and recreated every
    # table, including audit_chain_head, for test isolation. Recreate
    # the singleton row here so any test that triggers
    # record_audit_event() (directly or via a route) doesn't hit
    # NoResultFound on a table that's technically present but empty.
    audit.ensure_audit_chain_head(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db_session):
    """
    Minimal hand-built fixture, independent of backend/fixtures.json:
    one event/criterion/project, Judge A assigned + scored, Judge B
    unassigned and score-less, one organizer.
    """
    event = models.Event(
        name="Test Event",
        submission_opens_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        submission_closes_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db_session.add(event)
    db_session.flush()

    criterion = models.RubricCriterion(
        event_id=event.id, name="Innovation", weight=1.0, max_score=5
    )
    db_session.add(criterion)

    team = models.Team(event_id=event.id, name="Team Test")
    db_session.add(team)
    db_session.flush()

    project = models.Project(team_id=team.id, title="Test Project", status="submitted")
    db_session.add(project)
    db_session.flush()

    judge_a = models.User(
        email="judgea@test.local", password_hash=hash_password("pw"),
        role="judge", display_name="Judge A",
    )
    judge_b = models.User(
        email="judgeb@test.local", password_hash=hash_password("pw"),
        role="judge", display_name="Judge B",
    )
    organizer = models.User(
        email="org@test.local", password_hash=hash_password("pw"),
        role="organizer", display_name="Org",
    )
    db_session.add_all([judge_a, judge_b, organizer])
    db_session.flush()

    db_session.add(models.Assignment(judge_id=judge_a.id, project_id=project.id))
    db_session.add(models.Score(
        judge_id=judge_a.id, project_id=project.id,
        criterion_id=criterion.id, value=4,
    ))
    db_session.commit()

    return {
        "event": event, "project": project, "criterion": criterion,
        "judge_a": judge_a, "judge_b": judge_b, "organizer": organizer,
    }


def login(client: TestClient, email: str, password: str = "pw"):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp


def fresh_client() -> TestClient:
    """A new TestClient has its own cookie jar, so use one per logged-in
    identity rather than reusing/clearing a shared client's cookies."""
    return TestClient(app)

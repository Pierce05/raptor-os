from .conftest import fresh_client, login


def test_organizer_current_event(seeded):
    client = fresh_client()
    login(client, seeded["organizer"].email)
    resp = client.get("/api/organizer/event")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == seeded["event"].id


def test_judge_forbidden_from_current_event(seeded):
    """Not part of the original ask, but cheap to confirm: this route
    reuses require_organizer, so it should not be readable by a judge."""
    client = fresh_client()
    login(client, seeded["judge_a"].email)
    resp = client.get("/api/organizer/event")
    assert resp.status_code == 403


def test_participant_mine_returns_existing_project(db_session, seeded):
    from app import models

    # `seeded` doesn't put the participant on a team; build a minimal
    # participant + team + project here.
    from app.security import hash_password

    participant = models.User(
        email="participant2@test.local",
        password_hash=hash_password("pw"),
        role="participant",
        display_name="Participant",
    )
    db_session.add(participant)
    db_session.flush()
    db_session.add(models.TeamMember(team_id=seeded["project"].team_id, user_id=participant.id))
    db_session.commit()

    client = fresh_client()
    login(client, participant.email)
    resp = client.get("/api/projects/mine")
    assert resp.status_code == 200
    assert resp.json()["id"] == seeded["project"].id


def test_participant_mine_returns_null_with_no_project(db_session, seeded):
    from app import models
    from app.security import hash_password

    lonely_team = models.Team(event_id=seeded["event"].id, name="No Project Yet")
    db_session.add(lonely_team)
    db_session.flush()

    participant = models.User(
        email="participant3@test.local",
        password_hash=hash_password("pw"),
        role="participant",
        display_name="Participant",
    )
    db_session.add(participant)
    db_session.flush()
    db_session.add(models.TeamMember(team_id=lonely_team.id, user_id=participant.id))
    db_session.commit()

    client = fresh_client()
    login(client, participant.email)
    resp = client.get("/api/projects/mine")
    assert resp.status_code == 200
    assert resp.json() is None

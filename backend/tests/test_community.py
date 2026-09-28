"""T3-lite: community voting, ballot, results visibility, comments, audit."""
import re
import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, func

from app import audit, models
from app.security import hash_password
from tests.conftest import fresh_client, login

H = timedelta(hours=1)


def _user(db, email, role, name=None):
    u = models.User(email=email, password_hash=hash_password("pw"), role=role,
                    display_name=name or email.split("@")[0])
    db.add(u)
    db.flush()
    return u


@pytest.fixture()
def comm(db_session):
    db = db_session
    event = models.Event(
        name="Community Event",
        submission_opens_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        submission_closes_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db.add(event)
    db.flush()
    owner = _user(db, "owner@t.local", "participant")
    projects = []
    for i in range(7):
        team = models.Team(event_id=event.id, name=f"Team {i}")
        db.add(team)
        db.flush()
        if i == 0:
            db.add(models.TeamMember(team_id=team.id, user_id=owner.id))
        p = models.Project(team_id=team.id, title=f"Project {i}", status="submitted")
        db.add(p)
        db.flush()
        projects.append(p)
    users = {
        "owner": owner,
        "voter": _user(db, "voter@t.local", "participant"),
        "voter2": _user(db, "voter2@t.local", "participant"),
        "judge": _user(db, "judge@t.local", "judge"),
        "organizer": _user(db, "org@t.local", "organizer"),
    }
    db.commit()
    return {"event": event, "projects": projects, "users": users, "db": db}


def set_window(db, event, open_off, close_off):
    now = datetime.now(timezone.utc)
    w = db.get(models.VotingWindow, event.id)
    if w is None:
        w = models.VotingWindow(event_id=event.id)
        db.add(w)
    w.open_at, w.close_at = now + open_off, now + close_off
    db.commit()


def open_window(c):
    set_window(c["db"], c["event"], -H, H)


def client_for(c, who):
    cl = fresh_client()
    login(cl, c["users"][who].email)
    return cl


def actions(db):
    db.expire_all()
    return [a for (a,) in db.execute(select(models.AuditEvent.action).order_by(models.AuditEvent.seq))]


def vote(cl, project):
    return cl.post("/api/community/votes", json={"project_id": project.id})


# ---- window state -----------------------------------------------------------

def test_window_states(comm):
    cl = fresh_client()
    assert cl.get("/api/community/status").json()["state"] == "NOT_CONFIGURED"
    set_window(comm["db"], comm["event"], H, 2 * H)
    assert cl.get("/api/community/status").json()["state"] == "NOT_OPEN"
    open_window(comm)
    assert cl.get("/api/community/status").json()["state"] == "OPEN"
    set_window(comm["db"], comm["event"], -2 * H, -H)
    assert cl.get("/api/community/status").json()["state"] == "CLOSED"


def test_organizer_sets_window_audited_and_others_cannot(comm):
    now = datetime.now(timezone.utc)
    body = {"open_at": (now - H).isoformat(), "close_at": (now + H).isoformat()}
    assert client_for(comm, "voter").put("/api/organizer/community/window", json=body).status_code == 403
    org = client_for(comm, "organizer")
    r = org.put("/api/organizer/community/window", json=body)
    assert r.status_code == 200 and r.json()["state"] == "OPEN"
    bad = org.put("/api/organizer/community/window",
                  json={"open_at": body["close_at"], "close_at": body["open_at"]})
    assert bad.status_code == 422
    assert "voting_window.set" in actions(comm["db"])


# ---- voting ---------------------------------------------------------------------

def test_vote_ok_in_window(comm):
    open_window(comm)
    r = vote(client_for(comm, "voter"), comm["projects"][1])
    assert r.status_code == 200
    assert r.json()["voted_project_ids"] == [comm["projects"][1].id]
    assert "vote.accepted" in actions(comm["db"])


def test_judge_can_vote_organizer_cannot(comm):
    open_window(comm)
    assert vote(client_for(comm, "judge"), comm["projects"][1]).status_code == 200
    assert vote(client_for(comm, "organizer"), comm["projects"][1]).status_code == 403
    assert vote(fresh_client(), comm["projects"][1]).status_code == 401


def test_rejected_before_open_and_after_close(comm):
    cl = client_for(comm, "voter")
    set_window(comm["db"], comm["event"], H, 2 * H)
    assert vote(cl, comm["projects"][1]).status_code == 403
    set_window(comm["db"], comm["event"], -2 * H, -H)
    assert vote(cl, comm["projects"][1]).status_code == 403
    assert actions(comm["db"]).count("vote.window_rejected") == 2


def test_not_configured_rejected(comm):
    assert vote(client_for(comm, "voter"), comm["projects"][1]).status_code == 403


def test_duplicate_409(comm):
    open_window(comm)
    cl = client_for(comm, "voter")
    assert vote(cl, comm["projects"][1]).status_code == 200
    assert vote(cl, comm["projects"][1]).status_code == 409
    assert "vote.duplicate_rejected" in actions(comm["db"])


def test_own_team_rejected(comm):
    open_window(comm)
    r = vote(client_for(comm, "owner"), comm["projects"][0])
    assert r.status_code == 403
    assert "vote.own_team_rejected" in actions(comm["db"])


def test_sixth_vote_rejected(comm):
    open_window(comm)
    cl = client_for(comm, "voter")
    for p in comm["projects"][1:6]:
        assert vote(cl, p).status_code == 200
    r = vote(cl, comm["projects"][6])
    assert r.status_code == 403
    comm["db"].expire_all()
    n = comm["db"].execute(select(func.count()).select_from(models.Vote)).scalar_one()
    assert n == 5
    assert "vote.cap_rejected" in actions(comm["db"])


def test_rejected_vote_rate_limit_429(comm):
    open_window(comm)
    cl = client_for(comm, "voter")
    assert vote(cl, comm["projects"][1]).status_code == 200
    for _ in range(10):
        assert vote(cl, comm["projects"][1]).status_code == 409
    assert vote(cl, comm["projects"][1]).status_code == 429
    assert "vote.rate_limited" in actions(comm["db"])


def test_unknown_project_404(comm):
    open_window(comm)
    r = client_for(comm, "voter").post("/api/community/votes", json={"project_id": "nope"})
    assert r.status_code == 404


# ---- results visibility -----------------------------------------------------

def test_results_hidden_while_open_except_organizer(comm):
    open_window(comm)
    assert vote(client_for(comm, "voter"), comm["projects"][1]).status_code == 200
    for who in (None, "voter", "judge", "owner"):
        cl = fresh_client() if who is None else client_for(comm, who)
        r = cl.get("/api/community/results")
        assert r.status_code == 403, who
        assert "hidden until voting closes" in r.json()["detail"]
    org = client_for(comm, "organizer")
    r = org.get("/api/community/results")
    assert r.status_code == 200
    top = r.json()["results"][0]
    assert top["project_id"] == comm["projects"][1].id and top["votes"] == 1


def test_results_public_after_close(comm):
    open_window(comm)
    assert vote(client_for(comm, "voter"), comm["projects"][1]).status_code == 200
    set_window(comm["db"], comm["event"], -2 * H, -H)
    r = fresh_client().get("/api/community/results")
    assert r.status_code == 200
    assert r.json()["results"][0]["votes"] == 1


COUNT_KEY = re.compile(r"count|total|tally|^votes$|_votes$|^votes_|num_", re.I)


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_no_count_like_keys_in_other_payloads(comm):
    open_window(comm)
    cl = client_for(comm, "voter")
    p = comm["projects"][1]
    vote_resp = vote(cl, p)
    assert cl.post(f"/api/community/projects/{p.id}/comments", json={"body": "nice"}).status_code == 200
    payloads = {
        "gallery": fresh_client().get("/api/gallery").json(),
        "detail": fresh_client().get(f"/api/gallery/{p.id}").json(),
        "ballot": cl.get("/api/community/ballot").json(),
        "vote": vote_resp.json(),
        "comments": fresh_client().get(f"/api/community/projects/{p.id}/comments").json(),
        "status": fresh_client().get("/api/community/status").json(),
    }
    for name, body in payloads.items():
        bad = [k for k in _keys(body) if COUNT_KEY.search(k)]
        assert not bad, f"{name} leaks count-like keys: {bad}"


# ---- ballot -------------------------------------------------------------------

def test_ballot_order_differs_by_voter_and_is_stable(comm):
    open_window(comm)
    a, b = client_for(comm, "voter"), client_for(comm, "voter2")
    ids = lambda cl: [p["id"] for p in cl.get("/api/community/ballot").json()["projects"]]
    a1, a2, b1 = ids(a), ids(a), ids(b)
    assert a1 == a2
    assert a1 != b1
    assert sorted(a1) == sorted(b1)
    assert fresh_client().get("/api/community/ballot").status_code == 401


# ---- comments -------------------------------------------------------------------

def test_comment_create_and_limits(comm):
    p = comm["projects"][1]
    url = f"/api/community/projects/{p.id}/comments"
    assert fresh_client().post(url, json={"body": "hi"}).status_code == 401
    cl = client_for(comm, "voter")
    assert cl.post(url, json={"body": "x"}).status_code == 200
    assert cl.post(url, json={"body": "x" * 500}).status_code == 200
    assert cl.post(url, json={"body": ""}).status_code == 422
    assert cl.post(url, json={"body": "   "}).status_code == 422
    assert cl.post(url, json={"body": "x" * 501}).status_code == 422
    listed = fresh_client().get(url).json()
    assert len(listed) == 2 and listed[0]["author"] == "voter"
    assert "comment.created" in actions(comm["db"])


def test_comment_rate_limit(comm):
    p = comm["projects"][1]
    url = f"/api/community/projects/{p.id}/comments"
    cl = client_for(comm, "voter")
    for i in range(5):
        assert cl.post(url, json={"body": f"c{i}"}).status_code == 200
    assert cl.post(url, json={"body": "one too many"}).status_code == 429
    assert "comment.rate_limited" in actions(comm["db"])


# ---- audit ----------------------------------------------------------------------

def test_every_action_audited_and_chain_valid(comm):
    db = comm["db"]
    org = client_for(comm, "organizer")
    now = datetime.now(timezone.utc)
    org.put("/api/organizer/community/window",
            json={"open_at": (now - H).isoformat(), "close_at": (now + H).isoformat()})
    cl = client_for(comm, "voter")
    vote(cl, comm["projects"][1])
    vote(cl, comm["projects"][1])
    vote(client_for(comm, "owner"), comm["projects"][0])
    for p in comm["projects"][2:6]:
        vote(cl, p)
    vote(cl, comm["projects"][6])
    cl.post(f"/api/community/projects/{comm['projects'][1].id}/comments", json={"body": "hey"})
    set_window(db, comm["event"], H, 2 * H)
    vote(cl, comm["projects"][6])
    open_window(comm)
    for _ in range(11):
        vote(cl, comm["projects"][1])
    got = set(actions(db))
    for a in ("voting_window.set", "vote.accepted", "vote.duplicate_rejected", "vote.cap_rejected",
              "vote.window_rejected", "vote.own_team_rejected", "vote.rate_limited", "comment.created"):
        assert a in got, a
    ok, broken = audit.verify_chain(db)
    assert ok, broken


def test_organizer_summary_and_audit_endpoints(comm):
    open_window(comm)
    vote(client_for(comm, "voter"), comm["projects"][1])
    org = client_for(comm, "organizer")
    s = org.get("/api/organizer/community/summary").json()
    assert s["state"] == "OPEN" and s["total_votes"] == 1 and s["unique_voters"] == 1
    assert s["top_projects"][0]["votes"] == 1
    ev = org.get("/api/organizer/community/audit").json()["events"]
    assert any(e["action"] == "vote.accepted" and e["payload"] for e in ev)
    assert client_for(comm, "voter").get("/api/organizer/community/summary").status_code == 403


# ---- concurrency -------------------------------------------------------------

def test_threaded_duplicate_vote_race(comm):
    open_window(comm)
    login_client = client_for(comm, "voter")
    cookies = dict(login_client.cookies)
    target = comm["projects"][1]
    results, barrier = [], threading.Barrier(6)

    def worker():
        from fastapi.testclient import TestClient
        from app.main import app
        c = TestClient(app, cookies=cookies)
        barrier.wait()
        try:
            results.append(c.post("/api/community/votes", json={"project_id": target.id}).status_code)
        except Exception as exc:  # surface server-side errors instead of losing the thread
            results.append(f"EXC {type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(map(str, results)) == sorted(map(str, [200, 409, 409, 409, 409, 409])), results
    db = comm["db"]
    db.expire_all()
    assert db.execute(select(func.count()).select_from(models.Vote)).scalar_one() == 1
    acts = actions(db)
    assert acts.count("vote.accepted") == 1 and acts.count("vote.duplicate_rejected") == 5, acts
    ok, broken = audit.verify_chain(db)
    assert ok, broken

"""T4(c): HMAC-signed judge participation records."""
from sqlalchemy import select

from app import audit, config, models
from tests.conftest import fresh_client, login

SAFE_KEYS = {"name", "event", "reviews_completed", "issued_at", "audit_seq", "audit_hash", "signature_valid"}


def issue(seeded, judge_key="judge_a"):
    """Issue for one judge; returns (client, response-like with .json() == that judge's record)."""
    org = fresh_client()
    login(org, seeded["organizer"].email)
    r = org.post("/api/organizer/judge-records", json={"judge_id": seeded[judge_key].id})
    assert r.status_code == 200, r.text
    issued = r.json()["issued"]
    assert len(issued) == 1

    class _R:
        status_code = 200
        def json(self): return issued[0]
    return org, _R()


def test_issue_requires_organizer(seeded):
    assert fresh_client().post("/api/organizer/judge-records", json={"judge_id": "x"}).status_code == 401
    j = fresh_client()
    login(j, seeded["judge_a"].email)
    assert j.post("/api/organizer/judge-records", json={"judge_id": seeded["judge_a"].id}).status_code == 403


def test_issue_unknown_or_non_judge_404(seeded):
    org = fresh_client()
    login(org, seeded["organizer"].email)
    assert org.post("/api/organizer/judge-records", json={"judge_id": "nope"}).status_code == 404
    assert org.post("/api/organizer/judge-records", json={"judge_id": seeded["organizer"].id}).status_code == 404


def test_issue_for_all_judges_with_a_submitted_review(seeded, db_session):
    org = fresh_client()
    login(org, seeded["organizer"].email)
    r = org.post("/api/organizer/judge-records")            # no body: every eligible judge
    assert r.status_code == 200
    body = r.json()
    assert [x["name"] for x in body["issued"]] == ["Judge A"]          # A has 1 submitted review
    assert [(x["name"], x["reason"]) for x in body["skipped"]] == [("Judge B", "no_submitted_reviews")]
    # idempotent: nothing changed, so nothing new is issued
    again = org.post("/api/organizer/judge-records").json()
    assert again["issued"] == [] and {x["reason"] for x in again["skipped"]} == {"already_current", "no_submitted_reviews"}
    assert db_session.query(models.JudgeRecord).count() == 1


def test_naming_a_judge_without_reviews_issues_nothing(seeded, db_session):
    org = fresh_client()
    login(org, seeded["organizer"].email)
    body = org.post("/api/organizer/judge-records", json={"judge_id": seeded["judge_b"].id}).json()
    assert body["issued"] == [] and body["skipped"][0]["reason"] == "no_submitted_reviews"
    assert db_session.query(models.JudgeRecord).count() == 0


def test_record_is_anchored_to_its_audit_event(seeded, db_session):
    _, r = issue(seeded)
    rec = r.json()
    ev = db_session.execute(
        select(models.AuditEvent).where(models.AuditEvent.action == "judge_record.issued")
    ).scalar_one()
    assert rec["audit_seq"] == ev.seq and rec["audit_hash"] == ev.payload_hash and ev.entity_id == rec["id"]
    pub = fresh_client().get(f"/api/verify/{rec['id']}").json()
    assert pub["audit_seq"] == ev.seq and pub["audit_hash"] == ev.payload_hash


def test_tampered_audit_anchor_fails_verification(seeded, db_session):
    _, r = issue(seeded)
    rid = r.json()["id"]
    rec = db_session.get(models.JudgeRecord, rid)
    rec.audit_hash = "0" * 64
    db_session.commit()
    assert fresh_client().get(f"/api/verify/{rid}").json()["signature_valid"] is False
    rec.audit_hash = r.json()["audit_hash"]
    rec.audit_seq += 1
    db_session.commit()
    assert fresh_client().get(f"/api/verify/{rid}").json()["signature_valid"] is False


def test_issue_my_record_and_verify(seeded, db_session):
    _, r = issue(seeded)
    assert r.status_code == 200
    rec = r.json()
    assert rec["reviews_completed"] == 1 and rec["name"] == "Judge A" and rec["event"] == "Test Event"

    j = fresh_client()
    login(j, seeded["judge_a"].email)
    mine = j.get("/api/judge/record")
    assert mine.status_code == 200 and mine.json()["id"] == rec["id"]

    v = fresh_client().get(f"/api/verify/{rec['id']}")   # public, no auth
    assert v.status_code == 200
    body = v.json()
    assert set(body) == SAFE_KEYS and body["signature_valid"] is True
    assert body["reviews_completed"] == 1 and body["name"] == "Judge A"
    text = v.text.lower()
    for leak in ("score", "project", "criterion", "feedback", '"signature"'):
        assert leak not in text, leak
    assert "judge_record.issued" in [a for (a,) in db_session.execute(select(models.AuditEvent.action))]
    assert audit.verify_chain(db_session)[0]


def test_my_record_needs_judge_and_a_record(seeded):
    j = fresh_client()
    login(j, seeded["judge_b"].email)
    assert j.get("/api/judge/record").status_code == 404          # nothing issued to B
    assert fresh_client().get("/api/judge/record").status_code == 401
    o = fresh_client()
    login(o, seeded["organizer"].email)
    assert o.get("/api/judge/record").status_code == 403


def test_judge_cannot_read_someone_elses_record_via_my_record(seeded):
    issue(seeded, "judge_a")
    j = fresh_client()
    login(j, seeded["judge_b"].email)
    assert j.get("/api/judge/record").status_code == 404


def test_tampered_record_fails_verification(seeded, db_session):
    _, r = issue(seeded)
    rid = r.json()["id"]
    rec = db_session.get(models.JudgeRecord, rid)
    rec.reviews_completed = 99
    db_session.commit()
    assert fresh_client().get(f"/api/verify/{rid}").json()["signature_valid"] is False


def test_rotated_key_invalidates(seeded, monkeypatch):
    _, r = issue(seeded)
    rid = r.json()["id"]
    assert fresh_client().get(f"/api/verify/{rid}").json()["signature_valid"] is True
    monkeypatch.setattr(config, "RECORD_SIGNING_KEY", "some-other-key")
    assert fresh_client().get(f"/api/verify/{rid}").json()["signature_valid"] is False


def test_verify_unknown_id_404(seeded):
    assert fresh_client().get("/api/verify/does-not-exist").status_code == 404

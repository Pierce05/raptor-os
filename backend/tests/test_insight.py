"""Smoke tests for /api/organizer/insight/*: auth, shape, and the
seeded-baseline logic. Built on the `seeded` fixture in conftest.py."""
import pytest

from tests.conftest import fresh_client, login

PATHS = ["transformation", "calibration", "replay", "integrity", "public-vs-jury"]


def _org(seeded):
    c = fresh_client()
    login(c, "org@test.local")
    return c


@pytest.mark.parametrize("path", PATHS)
def test_insight_requires_organizer(seeded, path):
    anon = fresh_client()
    assert anon.get(f"/api/organizer/insight/{path}").status_code == 401
    judge = fresh_client()
    login(judge, "judgea@test.local")
    assert judge.get(f"/api/organizer/insight/{path}").status_code == 403


def test_insight_needs_a_normalization_run_first(seeded):
    c = _org(seeded)
    assert c.get("/api/organizer/insight/transformation").status_code == 400
    # replay and integrity work without a run
    assert c.get("/api/organizer/insight/replay").status_code == 200
    assert c.get("/api/organizer/insight/integrity").status_code == 200


def test_after_normalization_all_views_respond(seeded):
    c = _org(seeded)
    assert c.post("/api/organizer/normalization/run").status_code == 200
    pid = seeded["project"].id

    t = c.get("/api/organizer/insight/transformation").json()
    assert t["rows"] and t["rows"][0]["title"] == "Test Project"

    a = c.get(f"/api/organizer/insight/autopsy/{pid}")
    assert a.status_code == 200 and a.json()["headline"]

    cal = c.get("/api/organizer/insight/calibration").json()
    assert cal["judges"][0]["name"] == "Judge A"

    pj = c.get("/api/organizer/insight/public-vs-jury").json()
    assert pj["rows"][0]["votes"] == 0 and pj["correlation"] is None


def test_replay_chain_verifies_and_reports_seeded_baseline(seeded):
    c = _org(seeded)
    c.post("/api/organizer/normalization/run")
    r = c.get("/api/organizer/insight/replay").json()
    assert r["chain"]["valid"] is True
    assert all(e["verified"] for e in r["events"])
    # Judge A's score was inserted directly (no audit event) before the chain began.
    assert r["baseline"]["reviews"] == 1


def test_integrity_passes_on_clean_data_and_does_not_persist_recompute(seeded):
    c = _org(seeded)
    c.post("/api/organizer/normalization/run")
    body = c.get("/api/organizer/insight/integrity").json()
    by_id = {x["id"]: x for x in body["checks"]}
    assert by_id["audit_chain"]["status"] == "pass"
    assert by_id["scores_vs_audit"]["status"] == "pass"
    assert by_id["scores_vs_audit"]["evidence"]["predate_chain"] == 1
    assert by_id["normalization"]["status"] == "pass"
    assert body["not_evaluated"]
    # the reproducibility check must not have stored a second run
    from app.database import SessionLocal
    from app import models
    with SessionLocal() as s:
        assert s.query(models.NormalizationRun).count() == 1

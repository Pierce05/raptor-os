"""
Covers acceptance check T2.2: "Judge B cannot access Judge A's scores
-> 401/403". There is deliberately no route where a judge can pass an
arbitrary judge_id and read someone else's scores (see judge.py) -- so
this test targets the one route that legitimately accepts a judge_id
path parameter: the organizer-only peer-scores endpoint. A judge
session must be refused; only organizer/admin may use it.
"""
from .conftest import fresh_client, login


def test_judge_forbidden_from_peer_scores(seeded):
    judge_b_client = fresh_client()
    login(judge_b_client, seeded["judge_b"].email)

    resp = judge_b_client.get(
        f"/api/organizer/judges/{seeded['judge_a'].id}/scores",
        params={"project_id": seeded["project"].id},
    )
    assert resp.status_code == 403


def test_unauthenticated_forbidden_from_peer_scores(seeded):
    anon_client = fresh_client()
    resp = anon_client.get(
        f"/api/organizer/judges/{seeded['judge_a'].id}/scores",
        params={"project_id": seeded["project"].id},
    )
    assert resp.status_code == 401


def test_organizer_can_view_peer_scores(seeded):
    organizer_client = fresh_client()
    login(organizer_client, seeded["organizer"].email)

    resp = organizer_client.get(
        f"/api/organizer/judges/{seeded['judge_a'].id}/scores",
        params={"project_id": seeded["project"].id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["judge_id"] == seeded["judge_a"].id
    assert body["submitted"] == [
        {"criterion_id": seeded["criterion"].id, "value": 4.0}
    ]

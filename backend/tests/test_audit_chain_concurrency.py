"""
Covers finding #7: the audit hash chain's ordering/locking. Fires
several genuinely concurrent score submissions -- each a real HTTP
request, each acquiring its own DB connection via the app's normal
get_db() dependency -- and asserts that afterward the chain is (a)
still internally valid (verify_chain) and (b) has exactly one
contiguous, gap-free, duplicate-free seq per submission. Either kind of
corruption (a fork, a skipped seq, two events claiming the same seq)
would indicate the read-then-insert around the chain head wasn't
properly serialized.
"""
import threading

from app import models
from app.audit import verify_chain
from app.database import SessionLocal
from app.security import hash_password

from .conftest import fresh_client, login

N_WORKERS = 8


def _seed_concurrency_pairs(db_session, event):
    """
    N distinct (judge, project) pairs, each with its own assignment, so
    N concurrent score submissions are all independently legitimate --
    no immutability or unique-constraint collisions between them. The
    only thing genuinely contended between the N requests is the shared
    audit chain lock itself.
    """
    team = models.Team(event_id=event.id, name="Concurrency Team")
    db_session.add(team)
    db_session.flush()

    criterion = models.RubricCriterion(
        event_id=event.id, name="Concurrency Criterion", weight=1.0, max_score=5
    )
    db_session.add(criterion)
    db_session.flush()

    pairs = []
    for i in range(N_WORKERS):
        project = models.Project(
            team_id=team.id, title=f"Concurrent Project {i}", status="submitted"
        )
        judge = models.User(
            email=f"cjudge{i}@test.local",
            password_hash=hash_password("pw"),
            role="judge",
            display_name=f"Concurrent Judge {i}",
        )
        db_session.add_all([project, judge])
        db_session.flush()
        db_session.add(models.Assignment(judge_id=judge.id, project_id=project.id))
        pairs.append((judge, project))

    db_session.commit()
    return pairs, criterion


def test_concurrent_score_submissions_keep_chain_valid(db_session, seeded):
    pairs, criterion = _seed_concurrency_pairs(db_session, seeded["event"])

    results = [None] * len(pairs)

    def worker(i, judge, project):
        client = fresh_client()
        login(client, judge.email)
        resp = client.post(
            f"/api/judge/scores/{project.id}/submit",
            json={"scores": [{"criterion_id": criterion.id, "value": 3}]},
        )
        results[i] = resp.status_code

    threads = [
        threading.Thread(target=worker, args=(i, judge, project))
        for i, (judge, project) in enumerate(pairs)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(status == 200 for status in results), results

    verify_session = SessionLocal()
    try:
        ok, broken_id = verify_chain(verify_session)
        assert ok, f"chain broken at event {broken_id}"

        seqs = [
            e.seq
            for e in verify_session.query(models.AuditEvent).order_by(models.AuditEvent.seq).all()
        ]
    finally:
        verify_session.close()

    # Exactly one audit event per concurrent submission (the `seeded`
    # fixture inserts its one Score row directly via the ORM, bypassing
    # the API, so it contributes no audit event of its own here).
    # Contiguous 1..N with no gaps or duplicates is the actual proof
    # that concurrent writers did not fork or clobber the chain.
    assert len(seqs) == N_WORKERS
    assert seqs == list(range(1, N_WORKERS + 1))

import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import models


def _hash_payload(payload: dict, prev_hash: str | None) -> str:
    material = json.dumps(payload, sort_keys=True, default=str) + (prev_hash or "")
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    *,
    event_id: str | None,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
) -> models.AuditEvent:
    """
    Appends a tamper-evident audit event with a strictly ordered
    sequence number.

    Ordering and concurrency: the previous implementation found "the
    last event" via `ORDER BY created_at DESC LIMIT 1`, which has two
    problems under concurrent writers -- (1) created_at is not a
    reliable total order (two transactions can get the same timestamp,
    or commit out of timestamp order), and (2) a plain SELECT with no
    lock lets two concurrent transactions both read the same "last
    event" and both compute a next hash from it, forking the chain into
    two branches that each look internally valid.

    Both are fixed by taking a `SELECT ... FOR UPDATE` lock on the
    singleton AuditChainHead row before reading or writing anything.
    That row is always present (created at startup, see
    entrypoint.py), so even the very first audit event in the system's
    history serializes on it -- there is no "no previous row to lock"
    edge case. Whichever transaction acquires the lock first reads
    last_seq/last_hash, computes the next seq/hash, and updates the
    head; a second concurrent transaction blocks until the first
    commits (or rolls back), then sees the update and reads a
    consistent, un-forked chain.

    Must be called within the SAME db transaction as the mutation it
    documents (i.e. before commit), so a rollback of the mutation also
    rolls back its audit entry and releases the lock without having
    advanced the chain.
    """
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))

        head = db.execute(
            select(models.AuditChainHead)
            .where(models.AuditChainHead.id == 1)
        ).scalar_one()
    else:
        head = db.execute(
            select(models.AuditChainHead)
            .where(models.AuditChainHead.id == 1)
            .with_for_update()
        ).scalar_one()

    next_seq = head.last_seq + 1
    prev_hash = head.last_hash
    payload_hash = _hash_payload(payload, prev_hash)

    entry = models.AuditEvent(
        seq=next_seq,
        event_id=event_id,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
    )
    db.add(entry)

    head.last_seq = next_seq
    head.last_hash = payload_hash

    return entry


def ensure_audit_chain_head(db: Session) -> None:
    """
    Idempotently ensures the singleton AuditChainHead(id=1) row exists.
    Must run once at process startup, before any request can call
    record_audit_event() -- see that function's docstring for why the
    row must always be present (it's what every appender locks, even
    for the very first event ever recorded).
    """
    existing = db.get(models.AuditChainHead, 1)
    if existing is not None:
        return
    db.add(models.AuditChainHead(id=1, last_seq=0, last_hash=None))
    try:
        db.commit()
    except Exception:
        # Another process/worker won the race to create row id=1; that's
        # fine, it exists now either way.
        db.rollback()


def verify_chain(db: Session) -> tuple[bool, str | None]:
    """Recomputes the hash chain in seq order. Returns (ok, first_broken_event_id)."""
    events = db.execute(
        select(models.AuditEvent).order_by(models.AuditEvent.seq.asc())
    ).scalars().all()
    prev_hash = None
    expected_seq = 1
    for e in events:
        if e.seq != expected_seq:
            return False, e.id
        expected_seq += 1
        expected = _hash_payload(e.payload, prev_hash)
        if expected != e.payload_hash or e.prev_hash != prev_hash:
            return False, e.id
        prev_hash = e.payload_hash
    return True, None

"""
Scratch verification script (not part of the app) -- proves the audit
chain's locking *algorithm* is sound using nothing but stdlib sqlite3,
independent of SQLAlchemy/FastAPI (which aren't installable in this
sandbox). Two variants of the same read-then-insert pattern:

  - unlocked_record(): mirrors the OLD buggy design (ORDER BY
    created_at DESC LIMIT 1 with no lock) -- reads last_seq/last_hash
    with no lock, sleeps briefly (simulating real work between the read
    and the write, e.g. hashing + building the ORM object), then writes.
  - locked_record(): mirrors the NEW design in app/audit.py -- opens the
    write transaction with BEGIN IMMEDIATE *before* reading
    last_seq/last_hash (sqlite's equivalent of Postgres's
    SELECT ... FOR UPDATE: it takes a real write lock immediately,
    serializing all other writers until commit).

Both are run with N concurrent threads. Expected: unlocked forks/
duplicates seq values; locked produces exactly 1..N contiguous with no
gaps or dupes, every time.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time

N_THREADS = 12


def _hash_payload(payload, prev_hash):
    material = json.dumps(payload, sort_keys=True) + (prev_hash or "")
    return hashlib.sha256(material.encode()).hexdigest()


def make_db(path):
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("CREATE TABLE audit_chain_head (id INTEGER PRIMARY KEY, last_seq INTEGER, last_hash TEXT)")
    conn.execute("CREATE TABLE audit_event (id INTEGER PRIMARY KEY AUTOINCREMENT, seq INTEGER, prev_hash TEXT, payload_hash TEXT)")
    conn.execute("INSERT INTO audit_chain_head (id, last_seq, last_hash) VALUES (1, 0, NULL)")
    conn.commit()
    conn.close()


def unlocked_record(path, i, errors):
    """OLD pattern: no lock around read-then-write."""
    conn = sqlite3.connect(path, timeout=30)
    try:
        row = conn.execute("SELECT last_seq, last_hash FROM audit_chain_head WHERE id = 1").fetchone()
        last_seq, last_hash = row
        # Simulate real work happening between the read and the write
        # (building the ORM object, computing the hash) -- this is
        # exactly the window where a second thread can read the same
        # "last" state before the first thread commits its write.
        time.sleep(0.005)
        next_seq = last_seq + 1
        payload_hash = _hash_payload({"i": i}, last_hash)
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO audit_event (seq, prev_hash, payload_hash) VALUES (?, ?, ?)",
            (next_seq, last_hash, payload_hash),
        )
        conn.execute("UPDATE audit_chain_head SET last_seq = ?, last_hash = ? WHERE id = 1", (next_seq, payload_hash))
        conn.commit()
    except Exception as e:
        errors.append(str(e))
    finally:
        conn.close()


def locked_record(path, i, errors):
    """NEW pattern (mirrors app/audit.py): lock BEFORE reading."""
    conn = sqlite3.connect(path, timeout=30, isolation_level=None)  # manual transaction control
    try:
        conn.execute("BEGIN IMMEDIATE")  # sqlite's write-lock-now equivalent of SELECT...FOR UPDATE
        row = conn.execute("SELECT last_seq, last_hash FROM audit_chain_head WHERE id = 1").fetchone()
        last_seq, last_hash = row
        time.sleep(0.005)  # same simulated work window -- now safely inside the lock
        next_seq = last_seq + 1
        payload_hash = _hash_payload({"i": i}, last_hash)
        conn.execute(
            "INSERT INTO audit_event (seq, prev_hash, payload_hash) VALUES (?, ?, ?)",
            (next_seq, last_hash, payload_hash),
        )
        conn.execute("UPDATE audit_chain_head SET last_seq = ?, last_hash = ? WHERE id = 1", (next_seq, payload_hash))
        conn.commit()
    except Exception as e:
        errors.append(str(e))
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
    finally:
        conn.close()


def run_trial(record_fn, label):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    make_db(path)

    errors = []
    threads = [threading.Thread(target=record_fn, args=(path, i, errors)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    conn = sqlite3.connect(path, timeout=30)
    seqs = [r[0] for r in conn.execute("SELECT seq FROM audit_event ORDER BY seq")]
    conn.close()
    os.remove(path)

    duplicates = len(seqs) != len(set(seqs))
    contiguous = seqs == list(range(1, len(seqs) + 1))

    print(f"--- {label} ---")
    print(f"  threads: {N_THREADS}, events written: {len(seqs)}, errors: {len(errors)}")
    print(f"  seqs: {seqs}")
    print(f"  duplicates: {duplicates}, contiguous 1..N: {contiguous}")
    return duplicates, contiguous, len(seqs)


if __name__ == "__main__":
    dup_old, contig_old, n_old = run_trial(unlocked_record, "OLD unlocked pattern (expect forking)")
    dup_new, contig_new, n_new = run_trial(locked_record, "NEW BEGIN IMMEDIATE pattern (expect clean 1..N)")

    print()
    print("=== Verdict ===")
    old_broken = dup_old or not contig_old or n_old != N_THREADS
    new_ok = (not dup_new) and contig_new and n_new == N_THREADS
    print(f"OLD pattern showed corruption (forked/dup/missing seq): {old_broken}")
    print(f"NEW pattern stayed clean (contiguous, no dups, all {N_THREADS} recorded): {new_ok}")

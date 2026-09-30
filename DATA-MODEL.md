# Data model

See `backend/app/models.py` for the SQLAlchemy source of truth; this is
the narrative version.

```
Event ─┬─ Track
       ├─ RubricCriterion
       └─ NormalizationRun

Team ─┬─ TeamMember ── User
      ├─ Invitation
      └─ Project ─┬─ ProjectMedia
                   └─ Assignment ── User (judge)
                        └─ ScoreDraft / Score ── RubricCriterion

AuditEvent (hash-chained, references any entity)
```

## Key constraints

- `Assignment`: `UNIQUE(judge_id, project_id)` — a judge can't be
  double-assigned to the same project.
- `Score`: `UNIQUE(judge_id, project_id, criterion_id)` — a judge can't
  submit two scores for the same criterion on the same project. Scores
  are immutable once inserted; only `ScoreDraft` rows are mutable
  (upserted by composite primary key).
- `Event.fixture_sentinel`: unique, derived from a hash of the fixtures
  file content — this is what makes seeding idempotent across restarts,
  and correctly re-seeds if `fixtures.json` genuinely changes.

## Why fixtures.json doesn't dictate the schema

`fixtures.json` is treated purely as input data. `seed.py` transforms
it into our own relational shape; the DOGFOOD spec does not mandate a
schema, route names, or a database, so we designed the schema for our
own query patterns (fast role-scoped lookups, fast dashboard
aggregation) rather than mirroring the fixture format.

## Community and records tables (additive; no existing table changed)

```
Event ─┬─ VotingWindow            (one row per event: open_at, close_at)
       ├─ Vote                    (event, voter User, Project)
       └─ JudgeRecord             (judge User, HMAC signature)
Project ── Comment ── User (author)
```

- `voting_window(event_id PK, open_at, close_at)`. State
  (`NOT_CONFIGURED | NOT_OPEN | OPEN | CLOSED`) is computed at read time from
  server UTC; it is not stored.
- `vote(id, event_id, voter_id, project_id, created_at)` with
  `UNIQUE(event_id, voter_id, project_id)`. The 5-vote cap is enforced in
  code, under the audit-chain lock.
- `comment(id, project_id, author_id, body, created_at)`; body is 1-500
  characters, validated by the API.
- `judge_record(id, event_id, judge_id, judge_name, event_name,
  reviews_completed, issued_at, audit_seq, audit_hash, signature)`. The name,
  event and count are snapshotted at issue time. `audit_seq`/`audit_hash` are
  the sequence number and payload hash of the `judge_record.issued` audit event
  written in the same transaction. The HMAC covers id, name, event, count,
  issued_at, audit_seq and audit_hash, so editing any of them (or rotating
  `RECORD_SIGNING_KEY`) makes `signature_valid` false.
- Audit actions added: `voting_window.set`, `vote.accepted`,
  `vote.duplicate_rejected`, `vote.cap_rejected`, `vote.window_rejected`,
  `vote.own_team_rejected`, `vote.rate_limited`, `comment.created`,
  `comment.rate_limited`, `judge_record.issued`.

## Event export and what does NOT round-trip

`GET /api/organizer/export/event.json` (organizer only) emits
`{event, tracks, judges, teams, projects, scores}` in the `fixtures.json`
shape, so it can be loaded by the existing seeder. Ids in the output
(`trk_01`, `jdg_01`, ...) are positional labels, not database ids, so equality
is judged by content: project titles, member emails, and
(judge email, project title, criteria). `tests/test_export_roundtrip.py`
seeds, exports, loads the export into a fresh database, exports again, and
compares those structures.

These do **not** survive an export and re-seed:

- Votes, the voting window, and comments.
- The audit chain (a fresh database starts a new chain) and normalization runs.
- Passwords: every seeded account gets the fixed seed password again, and the
  organizer account is re-synthesized, not exported.
- Judge-to-track affinity (the seeder does not store it; exported as `[]`).
- Unsubmitted (draft) projects and their draft scores. Exported projects are
  all reloaded as submitted.
- Assignments that have no submitted score, and score timestamps.
- Project `submitted_at` (the seeder ignores it), `demo_url`, media, and the
  tagline/description split (both are exported as one `summary`).
- Rubric weights and max scores (the seeder regenerates equal weights).
- The submission opening time and the blind-judging flag (seeder defaults).
- Judge records and invitations.


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

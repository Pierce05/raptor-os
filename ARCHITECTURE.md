# Architecture

## One deployable monolith

FastAPI (backend) + PostgreSQL (storage) + React/Vite (frontend), served
as a single `docker compose up`. No microservices, no message queue, no
Redis, no external auth provider, no cloud dependency. Every added
service is an added failure surface in a 72-hour build; a monolith
keeps the failure surface to "is Postgres up" and "did the app boot."

The one exception to "single service" is the frontend static build,
which is its own container because a Vite build step and a Python
runtime don't belong in the same image. It is still zero external
dependencies: `frontend/Dockerfile` builds the React app with Node in
one stage and serves the static output with nginx in a second stage,
and nginx proxies `/api/*` to the `app` service over the internal
compose network. From the browser's point of view this is one origin
(`http://localhost:8080`) — the proxy is what keeps the session cookie
same-site without any CORS configuration mattering in production.

```
Browser --HTTP--> nginx (frontend, :8080) --static files--> React build
                        │
                        └--/api/*--> FastAPI app (:8000) --SQL--> PostgreSQL
```

## Why PostgreSQL, with an explicit SQLite fallback rule

The domain (users, teams, projects, assignments, scores) is strongly
relational and benefits from real foreign keys and unique constraints
(`UNIQUE(judge_id, project_id)`, `UNIQUE(judge_id, project_id,
criterion_id)`) enforced at the database level rather than in
application code.

**Fallback rule:** if Postgres tooling isn't reliably working (clean
`docker compose up` in under ~2 minutes) by hour 10, switch to SQLite
immediately rather than debugging further. The ORM layer isolates this
to a connection-string change.

## Authentication

Signed session cookie (Starlette `SessionMiddleware`), no external
identity provider. Login verifies a bcrypt hash and puts `user_id` in
the session. Every "who is asking" check derives the user from the
session — never from a client-supplied id in the query string or body.
That single rule is what keeps Judge B from reading Judge A's scores
(acceptance check #5) and what makes role isolation an API-level
guarantee rather than a hidden-button UI trick.

## Centralized guards

Two cross-cutting concerns are implemented once and called everywhere,
rather than duplicated per-route:

- `windows.assert_submission_window_open(event)` — deadline enforcement,
  checked against server time only.
- `audit.record_audit_event(...)` — called inside the same DB
  transaction as the mutation it documents, so a rollback also rolls
  back its audit trail.

## Assignment algorithm

Deterministic greedy assignment: repeatedly pick the least-reviewed
eligible project and the least-loaded eligible judge, skip existing
pairs (backstopped by a unique constraint), stop once every project
has `MIN_REVIEWS_PER_PROJECT` and no judge exceeds
`MAX_PROJECTS_PER_JUDGE`. No constraint solver — unnecessary at ~40
projects.

## Normalization and audit as first-class, versioned records

`NormalizationRun` stores the full input snapshot, parameters, and
results as one immutable row per run — never overwritten. This is what
makes "Explain This Ranking" cheap (read one row) and what makes
results defensible after the fact (you can always point to exactly
which run produced a given ranking).

`AuditEvent` forms an append-only hash chain
(`payload_hash = sha256(payload + prev_hash)`), ordered by an
app-assigned `seq` integer rather than `created_at` (timestamps aren't
a reliable total order under concurrent writers). Every append takes a
`SELECT ... FOR UPDATE` lock on a singleton `AuditChainHead` row before
reading "what's last" and inserting the next event, so concurrent
submissions serialize instead of forking the chain into two
internally-valid-looking branches. A tampered row is detectable because
every subsequent `prev_hash` stops matching; a forked or reordered
chain is detectable because `seq` stops being contiguous.

## What we deliberately did not build

Microservices, WebSockets, Redis, Kubernetes, an optimization solver
for assignment, a full Bayesian normalization model, community voting,
an AI judge. See the master blueprint's cut-order for the full
reasoning — every one of these was evaluated against acceptance-suite
risk, not feature appeal, and cut.

## Cut order under time pressure

1. Judging Replay
2. Mission Control visual polish
3. Blind judging
4. Keyboard shortcuts in the Command Deck
5. Normalization visualizer polish
6. Sophisticated (non-z-score) normalization
7. OpenAPI documentation bonus

**Never cut:** RBAC, deadline enforcement, idempotent fixture seeding,
public gallery, score isolation, CSV export, offline Docker boot.

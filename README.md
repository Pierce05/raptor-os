# RAPTOR-OS

*Judging you can explain.*

An open-source, self-hostable hackathon submission and judging system,
built for the DOGFOOD 2026 challenge. RAPTOR-OS turns judging from a
pile of disconnected score sheets into a fast, controlled, explainable,
auditable workflow.

## Quick start

```bash
docker compose up
```

That's it — no other setup, no network access required, nothing to
build or run by hand. Compose builds and starts three containers: the
Postgres database, the FastAPI backend, and the frontend (a Vite
production build served by nginx, which also proxies `/api/*` to the
backend so the browser only ever talks to one origin). The app seeds
itself from `backend/fixtures.json` on first boot (idempotently; safe
to restart).

- **App (open this in a browser): http://localhost:8080**
- Backend API directly (mostly for curl/scripts): http://localhost:8000
- Health check: http://localhost:8000/api/health
- Public gallery API: http://localhost:8000/api/gallery

> **TODO before submission:** `backend/fixtures.json` is still our own
> placeholder, not the organizer-provided fixture. Swap it for the real
> `fixtures.json` once DOGFOOD publishes it, and update `.dogfood.toml`
> and this table to match. Note: our placeholder's
> `submission_closes_at` is deliberately set in the **past** (not a
> convenient future date) specifically so the "closed event rejects
> submission" acceptance check has something real to exercise — keep
> that property (a closed window against at least one path) when you
> swap in the real fixture, even though the real event's actual dates
> will differ.

Seeded accounts (see `backend/fixtures.json` / `.dogfood.toml`):

| Role        | Email                  | Password          |
|-------------|-------------------------|--------------------|
| Organizer   | organizer@raptor.os     | organizer-pass     |
| Judge A     | judgea@raptor.os        | judgea-pass        |
| Judge B     | judgeb@raptor.os        | judgeb-pass        |
| Participant | participant@raptor.os   | participant-pass   |

## Local smoke test (ours, not the official checker)

Requires the stack to be up (`docker compose up`) since it makes real
HTTP requests against `http://localhost:8000`:

```bash
python3 scripts/local_acceptance_check.py
```

## Backend unit tests

Separate from the smoke test above -- these don't need the stack
running; they spin up an isolated sqlite DB per test run.

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Covers: RBAC on the organizer-only peer-scores route (T2 check #5),
zero-review projects surfacing correctly in normalization output, and
the audit hash chain staying valid under concurrent score submissions.

## `.dogfood.toml` cookies

Handled automatically: `docker compose up` includes a one-shot
`dogfood-toml` service that waits for the app to be healthy, logs in as
each seeded user, and rewrites the cookie fields in `.dogfood.toml` in
place. There is nothing to run by hand. `scripts/generate_dogfood_toml.sh`
still exists as a manual fallback (prints a single fresh cookie to
stdout) but isn't part of the normal flow anymore.

## Repo layout

```
backend/        FastAPI monolith (auth, RBAC, scoring, normalization, audit, CSV)
frontend/       React + Vite UI (gallery, judge deck, organizer console)
scripts/        Local test harness + cookie generation helper
docker-compose.yml
.dogfood.toml
ARCHITECTURE.md
DATA-MODEL.md
JUDGING.md       normalization formula + assumptions
THREAT-MODEL.md
```

## Design priorities

Correctness → T1 → T2 → hardening → signature features → bonuses → polish.
See `ARCHITECTURE.md` for the full reasoning and cut order.

## License

MIT — see `LICENSE`.

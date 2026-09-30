# API

Interactive docs are served by the app itself, under `/api` because the
frontend's nginx only proxies that prefix:

| URL | What |
|-----|------|
| `/api/docs` | Swagger UI |
| `/api/redoc` | ReDoc |
| `/api/openapi.json` | The schema |

`docs/openapi.json` is a committed copy. Regenerate it after changing any
route: `python3 scripts/export_openapi.py`. `backend/tests/test_openapi.py`
fails if the committed file differs from `app.openapi()`, and if any route
lacks a tag or summary.

## Auth

`POST /api/auth/login` sets a signed session cookie; every other identity
decision is made from that cookie, never from a client-supplied id.
Roles: `participant`, `judge`, `organizer`, `admin`.

## Route groups (tags)

| Tag | Prefix | Who |
|-----|--------|-----|
| auth | `/api/auth` | anyone / logged in |
| gallery | `/api/gallery` | public |
| teams, projects | `/api/teams`, `/api/projects` | participants |
| judge | `/api/judge` | judges (own data only) |
| organizer | `/api/organizer` | organizer/admin |
| community | `/api/community` | public status/comments/results-after-close; login to vote or comment |
| community-organizer | `/api/organizer/community` | organizer/admin |
| records-judge | `/api/judge/record` | judges |
| records-organizer | `/api/organizer/judge-records` | organizer/admin |
| verify | `/api/verify/{id}` | public |
| system | `/api/health` | public |

## Notable behaviors

- Vote results (`GET /api/community/results`) return 403 to everyone except
  organizer/admin until the window is CLOSED. No other payload carries counts.
- `GET /api/community/ballot` returns projects in a per-voter order computed
  by the server; the client cannot choose the order.
- `GET /api/organizer/export/event.json` returns the event in `fixtures.json`
  shape (see `DATA-MODEL.md` for what does not round-trip).
- `POST /api/organizer/judge-records` (no body) issues records for every judge
  with at least one submitted review and returns `{issued, skipped}`; an optional
  `judge_id` restricts it to one judge.
- `GET /api/verify/{id}` returns only name, event, reviews_completed,
  issued_at, audit_seq, audit_hash and signature_valid.
- Rate-limited or rejected actions return 429 / 403 / 409 and are audited.

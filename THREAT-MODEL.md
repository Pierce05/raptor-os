# Threat model

| Threat                     | Mitigation |
|-----------------------------|------------|
| IDOR (e.g. Judge B reading Judge A's scores) | Identity is always derived from the server-side session (`request.session["user_id"]`), never from a client-supplied id in a path/query/body param. See `deps.get_current_user`. |
| Privilege escalation        | Centralized RBAC via `require_role(...)` dependencies on every route; roles are read from the `User` row, not from client input. |
| Score tampering after submission | `Score` rows are immutable — the submit endpoint rejects a second submission for the same `(judge, project, criterion)` rather than overwriting. Only `ScoreDraft` is mutable. |
| Session theft               | Signed, httpOnly session cookie (Starlette `SessionMiddleware`); `same_site="lax"`. In a real deployment this needs `https_only=True` behind TLS — noted as a deployment hardening step, not implemented in local dev config. |
| Duplicate submissions        | `Project.status` transitions draft → submitted once; edit/submit endpoints reject non-draft projects. |
| Duplicate assignments        | `UNIQUE(judge_id, project_id)` DB constraint backstops the assignment algorithm's own duplicate check. |
| Duplicate scores             | `UNIQUE(judge_id, project_id, criterion_id)` DB constraint. |
| CSV injection                | Export uses Python's `csv` module, which quotes fields containing delimiters/quotes; no raw string concatenation into the CSV. Values are always numeric/UUID/title text pulled from trusted columns, not user-supplied formulas. |
| Fixture duplication on restart | `Event.fixture_sentinel` is a hash of the fixtures file content; re-seeding is a no-op unless the file actually changes. |
| Audit log tampering           | Append-only hash chain (`AuditEvent.payload_hash` / `prev_hash`), strictly ordered by an app-assigned `seq` (not `created_at`); `audit.verify_chain()` recomputes and detects any row whose stored hash, `prev_hash`, or `seq` no longer matches. |
| Audit chain forking under concurrent writes | Every append takes `SELECT ... FOR UPDATE` on the singleton `AuditChainHead` row before reading/writing, serializing concurrent submissions so two transactions can't both branch off the same "last event". Covered by `tests/test_audit_chain_concurrency.py`. |
| External data leakage         | No outbound network calls at runtime — no CDN fonts, no external APIs, no cloud auth. The app is designed to run with the container's network disabled. |
| Blind-judging identity leakage | Backend redacts team/member identity from the judge-facing project payload (not a frontend CSS trick). Documented limitation: repo/demo URLs are shown as-is and may still reveal identity. |

## Explicitly out of scope for this build

- DDoS protection / rate limiting (assumed to run behind organizer-controlled infra during judging, not internet-exposed).
- Multi-tenant isolation between different concurrent events (single-event assumption per deployment, consistent with DOGFOOD's scope).

## Community voting, comments and signed records (beyond T2, not claimed)

**This is members voting, not open public voting.** There is no
registration and no new role. Only the accounts that already exist (seeded
judges and team members) can vote or comment. Anyone who can obtain or share
one of those accounts' credentials can vote as that person.

| Threat | What is (and is not) done |
|--------|---------------------------|
| Ballot stuffing by one account | `UNIQUE(event_id, voter_id, project_id)`, a cap of 5 votes per voter, and a window check. Duplicate races are settled by the audit-chain lock plus the unique constraint. |
| Vote / comment flooding | A rolling 60 s limit counted from stored rows: 5 comments per user, and 10 rejected vote attempts per user (then 429). This only blunts abuse; it does not stop a patient attacker. |
| Voting for your own team | Rejected (403), audited as `vote.own_team_rejected`. Team membership is whatever the seed data says. |
| Early results leaking and steering votes | One function decides visibility (see JUDGING.md). Organizers/admins can always see live counts and are trusted not to leak them. |
| Ballot position bias | Per-voter seeded ordering. Not a security control (see JUDGING.md). |
| Server clock / client clock games | State comes from server UTC only. |
| Forged or edited judge records | HMAC-SHA256 over the record's public fields plus its id and audit-chain anchor (`audit_seq`, `audit_hash`), so a record can be cross-checked against the audit log entry that issued it. Verification is server-mediated: only the server holds `RECORD_SIGNING_KEY`, so a third party cannot verify offline. Rotating the key invalidates every issued record. The dev default key is public; a startup warning is logged while it is in use. |

**Not prevented.** Collusion (voters agreeing to trade votes) and account
farming (one person controlling several seeded accounts) are not prevented.
The caps and rate limits only make casual abuse harder.

**The audit log shows activity; it does not prevent it.** Every accepted and
rejected vote, comment, window change and record issuance is written to the
hash chain, which makes after-the-fact tampering detectable and lets an
organizer inspect suspicious patterns. It does not block anything by itself.
Comments are stored as plain text and rendered by React as text; there is no
moderation or deletion tool. Requests for unknown project ids return 404 and
are not audited.


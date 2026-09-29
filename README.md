

```markdown
# RAPTOR-OS

### Judging you can explain.

**RAPTOR-OS** is an open-source, self-hostable platform for running hackathons and technical competitions — from teams and submissions to judging, scoring, rankings, auditing, and public project discovery.

Built for **DOGFOOD 2026**, RAPTOR-OS turns judging from disconnected score sheets into a controlled, explainable workflow.

---

## ✦ What it does

| | Capability |
|---|---|
| 👥 | **Teams** — create teams and join through invite links |
| 📦 | **Submissions** — draft, edit, submit, and enforce deadlines |
| 🔍 | **Gallery** — public project discovery, search, and filtering |
| ⚖️ | **Judging** — assignments, weighted rubrics, and isolated scores |
| 📊 | **Scoring** — normalization, rankings, and CSV export |
| 🔐 | **RBAC** — Visitor, Participant, Judge, Organizer, Admin |
| 🧾 | **Auditability** — hash-chained event audit trail |
| 🗳️ | **Community** — voting, comments, randomized ballots |
| ✍️ | **Judge Records** — signed participation records + verification |
| 🔌 | **API** — FastAPI + OpenAPI |

---

## ✦ DOGFOOD 2026

RAPTOR-OS currently claims **T1 + T2** in `.dogfood.toml`.

### T1 — Submission & Event Infrastructure

- Authentication and sessions
- Five-role access model
- Event and track configuration
- Team formation through invite links
- Draft and editable submissions
- Server-side submission deadline enforcement
- Public project gallery
- Search and filtering

### T2 — Judging Infrastructure

- Judge assignment
- Weighted rubrics
- Judge/project isolation
- Live judging progress
- Score normalization
- CSV export

Additional functionality is implemented beyond the current T1/T2 claim.

---

## ✦ Built for Fairer Judging

RAPTOR-OS treats judging integrity as a system-level concern.

### Server-side isolation

Judges can access their assigned projects without accessing peer judges' scores.

### Auditable actions

Important competition actions generate audit events backed by a hash chain.

### Deadline enforcement

Submission deadlines are enforced by the backend, not just the frontend.

### Signed participation records

Judges can receive signed records of their participation, with server-mediated verification.

---

## ✦ Architecture

```text
                    RAPTOR-OS
                        │
             ┌──────────┴──────────┐
             │                     │
       React + Vite            FastAPI
        Frontend                Backend
             │                     │
             │              ┌──────┴──────┐
             │              │             │
             │           Auth/RBAC     Judging
             │              │             │
             │         Submissions    Scoring
             │              │             │
             │            Teams       Audit Log
             │              │             │
             └──────────────┴─────────────┘
                            │
                       PostgreSQL
```

### Stack

**Frontend:** React · Vite · Nginx  
**Backend:** Python · FastAPI · SQLAlchemy  
**Database:** PostgreSQL  
**Infrastructure:** Docker · Docker Compose  
**API:** REST · OpenAPI

---

## ✦ Screenshots

> Screenshots and a live demo can be added here.

| Gallery | Judge Deck |
|---|---|
| *coming soon* | *coming soon* |

| Participant Dashboard | Organizer Console |
|---|---|
| *coming soon* | *coming soon* |

---

## ✦ Quick Start

### Requirements

- Docker
- Docker Compose

### Run

```bash
git clone https://github.com/Pierce05/raptor-os.git
cd raptor-os
docker compose up
```

Open the application:

**http://localhost:8080**

Backend:

**http://localhost:8000**

API documentation:

**http://localhost:8000/api/docs**

Health check:

**http://localhost:8000/api/health**

The application seeds its development environment from `backend/fixtures.json`.

---

## ✦ Demo Accounts

| Role | Email | Password |
|---|---|---|
| Organizer | `organizer@raptor.os` | `organizer-pass` |
| Judge A | `judgea@raptor.os` | `judgea-pass` |
| Judge B | `judgeb@raptor.os` | `judgeb-pass` |
| Participant | `participant@raptor.os` | `participant-pass` |

These are the included local development fixtures.

---

## ✦ Documentation

| Document | Purpose |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System architecture |
| [`DATA-MODEL.md`](DATA-MODEL.md) | Database model |
| [`JUDGING.md`](JUDGING.md) | Judging & normalization |
| [`THREAT-MODEL.md`](THREAT-MODEL.md) | Security considerations |
| [`API.md`](API.md) | API overview |
| [`docs/openapi.json`](docs/openapi.json) | OpenAPI specification |

Interactive API docs are available at:

```text
/api/docs
/api/redoc
/api/openapi.json
```

---

## ✦ Testing

Run the local acceptance check with the stack running:

```bash
python3 scripts/local_acceptance_check.py
```

Run backend tests:

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

---

## ✦ Current Scope

RAPTOR-OS is designed as self-hostable competition infrastructure rather than a complete hosted SaaS product.

Current limitations include:

- Single event per deployment
- Seeded development accounts
- Authenticated/member community voting
- No CAPTCHA or email verification
- No webhook system
- No embeddable widget
- Participation records use server-mediated HMAC verification

These limitations are documented intentionally.

---

## ✦ Project

**RAPTOR-OS**  
*Open-source infrastructure for hackathons and technical competitions.*

Built for **DOGFOOD 2026**.

**Repository:**  
https://github.com/Pierce05/raptor-os

---

## License

MIT — see [`LICENSE`](LICENSE).
```

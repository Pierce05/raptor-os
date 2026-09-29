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
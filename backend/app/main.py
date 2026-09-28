import logging

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .database import Base, engine, SessionLocal
from . import audit
from .routers import auth, gallery, teams, projects, judge, organizer, community, organizer_community, records as records_routes

Base.metadata.create_all(bind=engine)

# The audit hash chain's singleton lock row must exist before any
# request can call record_audit_event() -- see audit.py. This runs
# once per process (production boot via entrypoint.py, `uvicorn
# app.main:app --reload` in dev, and TestClient(app) in tests all
# import this module and hit this line).
_startup_db = SessionLocal()
try:
    audit.ensure_audit_chain_head(_startup_db)
finally:
    _startup_db.close()

if config.RECORD_SIGNING_KEY == config.DEFAULT_RECORD_SIGNING_KEY:
    logging.getLogger("uvicorn.error").warning(
        "RECORD_SIGNING_KEY is unset: signing judge records with the public dev default. "
        "Set RECORD_SIGNING_KEY to a real secret before issuing records."
    )

app = FastAPI(
    title="RAPTOR-OS",
    version="1.0.0",
    description="Hackathon submission and judging portal. See API.md.",
    # nginx proxies only /api, so the schema and docs must live under it.
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET, same_site="lax")
app.add_middleware(
    CORSMiddleware,
    # Wildcard "*" is incompatible with allow_credentials=True (browsers
    # reject it). In `docker compose up`, the frontend's nginx proxies
    # /api same-origin (see frontend/nginx.conf), so the browser never
    # makes a cross-origin request there. This list only matters for the
    # Vite dev server (frontend/vite.config.js proxies /api too, so even
    # that is normally same-origin) or if something hits the API from a
    # different origin/port directly.
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(gallery.router)
app.include_router(teams.router)
app.include_router(projects.router)
app.include_router(judge.router)
app.include_router(organizer.router)
app.include_router(community.router)
app.include_router(organizer_community.router)
app.include_router(records_routes.organizer_router)
app.include_router(records_routes.judge_router)
app.include_router(records_routes.public_router)


@app.get("/api/health", tags=["system"], summary="Liveness check")
def health():
    return {"status": "ok"}

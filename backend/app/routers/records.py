import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import community as cm, models, records
from ..audit import record_audit_event
from ..database import get_db
from ..deps import require_judge, require_organizer
from ..seed import import_fixture_data

organizer_router = APIRouter(prefix="/api/organizer/judge-records", tags=["records-organizer"])
judge_router = APIRouter(prefix="/api/judge", tags=["records-judge"])
public_router = APIRouter(prefix="/api/verify", tags=["verify"])


class IssueIn(BaseModel):
    # Optional: omit to issue for every eligible judge; set to limit to one.
    judge_id: str | None = None


def _own_view(rec: models.JudgeRecord) -> dict:
    return {
        "id": rec.id, "name": rec.judge_name, "event": rec.event_name,
        "reviews_completed": rec.reviews_completed,
        "issued_at": records.issued_iso(rec.issued_at),
        "audit_seq": rec.audit_seq, "audit_hash": rec.audit_hash,
        "signature": rec.signature,
    }


def _submitted_counts(db: Session) -> dict[str, int]:
    """judge_id -> number of distinct projects with at least one submitted score."""
    rows = db.execute(
        select(models.Score.judge_id, func.count(func.distinct(models.Score.project_id)))
        .where(models.Score.submitted_at.is_not(None))
        .group_by(models.Score.judge_id)
    ).all()
    return {judge_id: n for judge_id, n in rows}


def _latest_for(db: Session, judge_id: str) -> models.JudgeRecord | None:
    return db.execute(
        select(models.JudgeRecord).where(models.JudgeRecord.judge_id == judge_id)
        .order_by(models.JudgeRecord.issued_at.desc(), models.JudgeRecord.id).limit(1)
    ).scalar_one_or_none()


@organizer_router.post(
    "",
    summary="Issue signed participation records for every judge with a submitted review (audited)",
)
def issue_records(
    body: IssueIn | None = None,
    user: models.User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    """Issues one record per judge with >=1 submitted review. Judges with none are
    skipped, and so are judges whose latest record already shows their current count
    (so re-running is idempotent). Pass judge_id to restrict to a single judge."""
    only = body.judge_id if body else None
    if only is not None:
        j = db.get(models.User, only)
        if j is None or j.role != "judge":
            raise HTTPException(status_code=404, detail="Judge not found")
    event = cm.single_event(db)
    counts = _submitted_counts(db)
    judges = db.execute(
        select(models.User).where(models.User.role == "judge").order_by(models.User.display_name, models.User.id)
    ).scalars().all()
    issued, skipped = [], []
    for judge in judges:
        if only is not None and judge.id != only:
            continue
        completed = counts.get(judge.id, 0)
        if completed < 1:
            skipped.append({"judge_id": judge.id, "name": judge.display_name, "reason": "no_submitted_reviews"})
            continue
        latest = _latest_for(db, judge.id)
        if latest is not None and latest.reviews_completed == completed:
            skipped.append({"judge_id": judge.id, "name": judge.display_name, "reason": "already_current"})
            continue
        rec_id = models.new_id()
        # Audit first: it takes the chain lock before any write. One audit event and one
        # commit per record (SQLite cannot start a second BEGIN IMMEDIATE after a write).
        entry = record_audit_event(
            db, event_id=event.id, actor_id=user.id, action="judge_record.issued",
            entity_type="judge_record", entity_id=rec_id,
            payload={"judge_id": judge.id, "reviews_completed": completed},
        )
        rec = models.JudgeRecord(
            id=rec_id, event_id=event.id, judge_id=judge.id, judge_name=judge.display_name,
            event_name=event.name, reviews_completed=completed,
            issued_at=datetime.now(timezone.utc).replace(microsecond=0),
            audit_seq=entry.seq, audit_hash=entry.payload_hash, signature="",
        )
        rec.signature = records.sign(rec)
        db.add(rec)
        db.commit()
        issued.append(_own_view(rec))
    return {"issued": issued, "skipped": skipped}

@organizer_router.post(
    "/import",
    summary="Import a fixtures.json-compatible event",
)
async def import_event(
    file: UploadFile = File(...),
    user: models.User = Depends(require_organizer),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400,
            detail="Only JSON fixture files are supported",
        )

    try:
        raw = await file.read()
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON file",
        )

    required = ("event", "tracks", "judges", "teams", "projects", "scores")

    if not all(key in data for key in required):
        raise HTTPException(
            status_code=400,
            detail="Invalid fixture format",
        )

    try:
        result = import_fixture_data(db, data)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Fixture import failed",
        )

    return {
        "ok": True,
        "imported": result,
    }

@judge_router.get("/record", summary="The calling judge's latest participation record (no id parameter)")
def my_record(user: models.User = Depends(require_judge), db: Session = Depends(get_db)):
    rec = _latest_for(db, user.id)
    if rec is None:
        raise HTTPException(status_code=404, detail="No record has been issued to you yet")
    return _own_view(rec)


@public_router.get("/{record_id}", summary="Public, server-mediated check of a participation record")
def verify_record(record_id: str, db: Session = Depends(get_db)):
    rec = db.get(models.JudgeRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return {
        "name": rec.judge_name, "event": rec.event_name,
        "reviews_completed": rec.reviews_completed,
        "issued_at": records.issued_iso(rec.issued_at),
        "audit_seq": rec.audit_seq, "audit_hash": rec.audit_hash,
        "signature_valid": records.signature_valid(rec),
    }

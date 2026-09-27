from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models


def _as_utc_aware(dt: datetime) -> datetime:
    """
    SQLAlchemy's SQLite dialect stores DateTime(timezone=True) values as
    plain ISO text and hands back a NAIVE datetime on read-back (SQLite
    has no native timestamptz type, so the timezone=True flag is a
    no-op on that backend) -- even though the value was originally
    written as UTC-aware. Postgres's psycopg2 driver does not have this
    problem and always returns a proper tz-aware datetime for
    timestamptz columns.

    Every event date in this app is written as UTC (see seed.py), so a
    naive value read back can be safely assumed to already be UTC and
    just needs tzinfo attached -- NOT converted, since it's already the
    right wall-clock time. Without this, comparing against
    datetime.now(timezone.utc) below raises
    "TypeError: can't compare offset-naive and offset-aware datetimes"
    on SQLite (dev/tests) while working fine on Postgres (production),
    which is exactly the kind of backend-specific bug that hides until
    someone tests against the "fallback" database.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def assert_submission_window_open(db: Session, event_id: str) -> None:
    """
    Single source of truth for the submission deadline. Every route that
    creates/edits/submits a project MUST call this rather than checking
    dates itself. Always compares against SERVER time, never a
    client-supplied timestamp.
    """
    event = db.get(models.Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    now = datetime.now(timezone.utc)
    opens_at = _as_utc_aware(event.submission_opens_at)
    closes_at = _as_utc_aware(event.submission_closes_at)
    if now < opens_at or now > closes_at:
        raise HTTPException(status_code=403, detail="Submission window is closed")

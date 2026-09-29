import json

from app import models
from app.export import build_event_export
from app.seed import import_fixture_data


def test_export_import_roundtrip(seeded, db_session):
    event = seeded["event"]

    exported = build_event_export(db_session, event)

    assert set(exported) == {
        "event",
        "tracks",
        "judges",
        "teams",
        "projects",
        "scores",
    }

    # Ensure the exported object is actually JSON-compatible.
    raw = json.dumps(exported)
    fixture_data = json.loads(raw)

    imported = import_fixture_data(db_session, fixture_data)

    assert imported["event_name"] == event.name
    assert imported["tracks"] == len(exported["tracks"])
    assert imported["judges"] == len(exported["judges"])
    assert imported["teams"] == len(exported["teams"])
    assert imported["projects"] == len(exported["projects"])
    assert imported["scores"] == len(exported["scores"])

    # Confirm the imported event actually exists.
    events = db_session.query(models.Event).all()
    assert len(events) == 2
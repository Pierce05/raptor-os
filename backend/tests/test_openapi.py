"""T4(a): OpenAPI is served under /api, every operation is documented, and
the committed docs/openapi.json has not drifted from app.openapi()."""
import json
from pathlib import Path

from app.main import app
from tests.conftest import fresh_client

COMMITTED = Path(__file__).resolve().parents[2] / "docs" / "openapi.json"
METHODS = {"get", "post", "put", "patch", "delete"}


def test_openapi_and_docs_served_under_api():
    c = fresh_client()
    r = c.get("/api/openapi.json")
    assert r.status_code == 200 and r.json()["openapi"].startswith("3.")
    assert c.get("/api/docs").status_code == 200


def test_every_operation_has_tags_and_summary():
    missing = []
    for path, item in app.openapi()["paths"].items():
        for method, op in item.items():
            if method in METHODS and not (op.get("tags") and op.get("summary")):
                missing.append(f"{method.upper()} {path}")
    assert not missing, missing


def test_committed_openapi_matches_app():
    assert COMMITTED.exists(), "run: python3 scripts/export_openapi.py"
    committed = json.loads(COMMITTED.read_text())
    assert committed == json.loads(json.dumps(app.openapi())), (
        "docs/openapi.json is stale; run: python3 scripts/export_openapi.py"
    )

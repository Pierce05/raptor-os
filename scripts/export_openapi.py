#!/usr/bin/env python3
"""Write docs/openapi.json from app.openapi().

Usage (from the repo root):  python3 scripts/export_openapi.py

Needs no running server and no Postgres: it points the app at a throwaway
SQLite file unless DATABASE_URL is already set, because importing
app.main creates tables.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

if "DATABASE_URL" not in os.environ:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
os.environ.setdefault("SEED_ON_START", "false")

from app.main import app  # noqa: E402


def main() -> None:
    out = ROOT / "docs" / "openapi.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

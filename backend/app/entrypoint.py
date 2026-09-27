"""
Container entrypoint: creates tables, seeds fixtures idempotently, then
launches uvicorn. Kept separate from main.py so `main:app` stays a plain
importable ASGI app for tests/dev (`uvicorn app.main:app --reload`).
"""
import uvicorn

from . import config
from .database import Base, engine, SessionLocal
from . import seed


def run():
    Base.metadata.create_all(bind=engine)
    if config.SEED_ON_START:
        db = SessionLocal()
        try:
            seed.seed_from_file(db, config.FIXTURES_PATH)
        finally:
            db.close()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()

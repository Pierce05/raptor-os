from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from . import config

# check_same_thread=False + a generous busy timeout only matter for the
# sqlite backend used by the test suite (production always uses
# postgresql+psycopg2, see docker-compose.yml). Tests exercise multiple
# threads sharing one sqlite file to fire concurrent requests at the
# audit hash chain's row lock (see tests/test_audit_chain_concurrency.py);
# without a longer busy timeout, sqlite's whole-file write lock can
# surface as a transient "database is locked" error under that
# contention instead of the caller simply waiting its turn.
_connect_args = {}
if config.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False, "timeout": 30}

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

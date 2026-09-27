import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://raptor:raptor@localhost:5432/raptor"
)
SESSION_SECRET = os.environ.get("SESSION_SECRET", "dev-secret-change-me")
FIXTURES_PATH = os.environ.get("FIXTURES_PATH", "./fixtures.json")
SEED_ON_START = os.environ.get("SEED_ON_START", "true").lower() == "true"

# Normalization defaults (see JUDGING.md for the full derivation)
NORMALIZATION_MIN_SAMPLES = int(os.environ.get("NORMALIZATION_MIN_SAMPLES", "5"))
NORMALIZATION_SHRINKAGE_K = float(os.environ.get("NORMALIZATION_SHRINKAGE_K", "5"))

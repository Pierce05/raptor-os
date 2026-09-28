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

# T3-lite community voting. Constants, never per-request input.
VOTE_CAP_PER_VOTER = 5
# Mixed into the per-voter ballot hash. Override in production.
BALLOT_SEED = os.environ.get("BALLOT_SEED", "dev-ballot-seed-change-me")
# Rolling-window limits (window is COMMUNITY_RATE_WINDOW_SECONDS).
COMMUNITY_RATE_WINDOW_SECONDS = 60
COMMENT_RATE_LIMIT = 5            # comments per user per window
REJECTED_VOTE_RATE_LIMIT = 10     # rejected vote attempts per user per window
COMMENT_MAX_LEN = 500

# T4(c) judge participation records. HMAC key for signing them.
# The dev default is public knowledge (it is in this repo): set a real secret
# in any deployment. main.py logs a startup warning while the default is in use.
DEFAULT_RECORD_SIGNING_KEY = "dev-record-signing-key-change-me"
RECORD_SIGNING_KEY = os.environ.get("RECORD_SIGNING_KEY", DEFAULT_RECORD_SIGNING_KEY)

#!/usr/bin/env bash
# Manual fallback only. `docker compose up` now regenerates
# .dogfood.toml's cookies automatically via the `dogfood-toml` compose
# service (see scripts/regenerate_dogfood_cookies.py) -- you should not
# normally need this script. It's kept for grabbing a single fresh
# cookie by hand (e.g. for a manual curl session) without restarting
# the whole stack. Requires the app to be up at http://localhost:8000.
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

login() {
  local email="$1" password="$2"
  curl -s -c - -o /dev/null \
    -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$email\", \"password\": \"$password\"}" \
    | awk '/session/ {print $NF}'
}

echo "participant cookie: $(login participant@raptor.os participant-pass)"
echo "judge_a cookie:      $(login judgea@raptor.os judgea-pass)"
echo "judge_b cookie:      $(login judgeb@raptor.os judgeb-pass)"
echo "organizer cookie:    $(login organizer@raptor.os organizer-pass)"
echo
echo "Paste these into .dogfood.toml in place of REPLACE_ME."

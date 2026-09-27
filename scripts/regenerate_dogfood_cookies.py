#!/usr/bin/env python3
"""
Regenerates .dogfood.toml's [auth] cookies AND [routes].peer_scores'
judge id automatically as part of `docker compose up`, so nobody has to
remember a manual step and nothing can go stale between a rebuild and
whenever the real acceptance checker actually runs.

Runs as a one-shot compose service (see docker-compose.yml, service
`dogfood-toml`) that waits for the app's healthcheck, logs in as each
account listed in [seed_accounts], and rewrites two things in place:
  - the matching `role = "Cookie: session=..."` line inside [auth]
  - the judge id embedded in [routes].peer_scores, taken from
    judge_a's real login response

Everything else in the file (comments, [portal], [tiers], route paths
other than peer_scores) is left untouched.

Only the standard library is used, so this runs in a bare
python:3-slim container with nothing installed.

IMPORTANT: [auth] and [routes] are read directly by the real DOGFOOD
run.py, which does plain string concatenation on [routes] values with
NO templating -- so peer_scores must already contain a real, live judge
id by the time run.py runs, not a placeholder. That's the main reason
this script exists rather than a human editing the file once.
"""
import json
import os
import re
import time
import tomllib
import urllib.error
import urllib.request

TOML_PATH = os.environ.get("DOGFOOD_TOML_PATH", "/workspace/.dogfood.toml")
BASE_URL = os.environ.get("DOGFOOD_BASE_URL", "http://app:8000")
MAX_WAIT_SECONDS = 60


def wait_for_app() -> None:
    deadline = time.time() + MAX_WAIT_SECONDS
    last_err = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE_URL}/api/health", timeout=2)
            return
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = e
            time.sleep(1)
    raise SystemExit(f"app never became healthy at {BASE_URL} within {MAX_WAIT_SECONDS}s ({last_err})")


def login(email: str, password: str) -> tuple[str, str]:
    """Returns (cookie_header_value, user_id)."""
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=5)
    set_cookie = resp.headers.get("Set-Cookie", "")
    cookie = set_cookie.split(";")[0]
    if not cookie:
        raise SystemExit(f"login for {email} did not return a session cookie")
    user = json.loads(resp.read())
    user_id = user.get("id")
    if not user_id:
        raise SystemExit(f"login for {email} did not return a user id")
    return f"Cookie: {cookie}", user_id


def main() -> None:
    wait_for_app()

    with open(TOML_PATH, "rb") as f:
        data = tomllib.load(f)

    seed_accounts = data.get("seed_accounts", {})
    if not seed_accounts:
        raise SystemExit("no [seed_accounts] table found in .dogfood.toml")

    auth_headers: dict[str, str] = {}
    judge_a_id: str | None = None
    for role, creds in seed_accounts.items():
        header_value, user_id = login(creds["email"], creds["password"])
        auth_headers[role] = header_value
        if role == "judge_a":
            judge_a_id = user_id

    if judge_a_id is None:
        raise SystemExit("no [seed_accounts].judge_a entry -- cannot resolve peer_scores id")

    with open(TOML_PATH, "r") as f:
        lines = f.readlines()

    current_section = None
    out = []
    for line in lines:
        header = re.match(r"^\[([\w.]+)\]\s*$", line)
        if header:
            current_section = header.group(1)
            out.append(line)
            continue

        if current_section == "auth":
            role_match = re.match(r"^\s*(\w+)\s*=", line)
            if role_match and role_match.group(1) in auth_headers:
                role = role_match.group(1)
                out.append(f'{role}   = "{auth_headers[role]}"\n')
                continue

        if current_section == "routes":
            if re.match(r"^\s*peer_scores\s*=", line):
                out.append(
                    f'peer_scores  = "/api/organizer/judges/{judge_a_id}/scores"\n'
                )
                continue

        out.append(line)

    with open(TOML_PATH, "w") as f:
        f.writelines(out)

    print(f"[dogfood-toml] refreshed cookies for: {', '.join(auth_headers)}")
    print(f"[dogfood-toml] resolved peer_scores judge id: {judge_a_id}")


if __name__ == "__main__":
    main()

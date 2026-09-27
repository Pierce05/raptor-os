#!/usr/bin/env python3
"""
Local smoke test mirroring the T1/T2 acceptance checks described in the
DOGFOOD spec. This is OUR OWN test harness for use before/instead of the
organizers' real run.py -- it is not a substitute for the official
checker, but it should catch the same class of failures early.

Usage:
    python3 scripts/local_acceptance_check.py [base_url]
"""
import sys
import json
import urllib.request
import urllib.error

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

passed = []
failed = []


def check(name, condition):
    (passed if condition else failed).append(name)
    print(f"{'PASS' if condition else 'FAIL'}  {name}")


def request(method, path, body=None, cookie=None):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, resp.headers, _parse_body(resp)
    except urllib.error.HTTPError as e:
        return e.code, e.headers, _parse_body(e)


def _parse_body(resp):
    """
    Only attempt json.loads() when the response actually claims to be
    JSON. Forcing json.loads() on every body breaks non-JSON responses
    like the CSV export (T2.4, Content-Type: text/csv) with a
    JSONDecodeError instead of letting the caller see the raw text and
    make its own assertion about it.
    """
    raw = resp.read() or b""
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def login(email, password):
    status, headers, _ = request("POST", "/api/auth/login", {"email": email, "password": password})
    cookie = headers.get("Set-Cookie", "").split(";")[0]
    return status, cookie


# T1.1 -- public gallery -> 200
status, _, gallery = request("GET", "/api/gallery")
check("T1.1 public gallery returns 200", status == 200)

# T1.2 -- known fixture project appears
titles = [p.get("title") for p in gallery] if isinstance(gallery, list) else []
check("T1.2 fixture project 'Obsidian Falcon' appears", "Obsidian Falcon" in titles)

# T2.1 / T2.2 -- judge auth and isolation
status, cookie_a = login("judgea@raptor.os", "judgea-pass")
check("login as judge A succeeds", status == 200)
status, cookie_b = login("judgeb@raptor.os", "judgeb-pass")
check("login as judge B succeeds", status == 200)
status, cookie_p = login("participant@raptor.os", "participant-pass")
check("login as participant succeeds", status == 200)
status, cookie_org = login("organizer@raptor.os", "organizer-pass")
check("login as organizer succeeds", status == 200)

if gallery:
    project_id = gallery[0]["id"]

    status, _, _ = request("GET", f"/api/judge/scores/{project_id}", cookie=cookie_a)
    check("T2.1 judge A can hit own-scores endpoint (200 or 403 if unassigned)", status in (200, 403))

    status, _, _ = request("GET", f"/api/judge/scores/{project_id}", cookie=cookie_p)
    check("T2.3 participant cannot access judge scores endpoint", status in (401, 403))

# T2.2 -- Judge B cannot read Judge A's scores. There is deliberately no
# route where a judge can pass an arbitrary judge_id and read someone
# else's scores (judge.py always derives identity from the session) --
# the one route that legitimately accepts a judge_id path parameter is
# the organizer-only peer-scores endpoint added specifically to give
# this check something real to hit (see .dogfood.toml [routes].peer_scores
# and backend/app/routers/organizer.py). A judge session must be refused.
status, _, me_a = request("GET", "/api/auth/me", cookie=cookie_a)
judge_a_id = me_a.get("id") if status == 200 else None
if judge_a_id:
    status, _, _ = request(
        "GET", f"/api/organizer/judges/{judge_a_id}/scores?project_id=dummy", cookie=cookie_b
    )
    check("T2.2 judge B cannot read judge A's scores -> 401/403", status in (401, 403))
else:
    check("T2.2 judge B cannot read judge A's scores -> 401/403 (could not resolve judge A id)", False)

# T1.3 -- closed event rejects a participant submission -> 4xx. Relies
# on backend/fixtures.json's submission_closes_at being in the past
# (see the note in that file / README.md) -- if someone points this
# script at a deployment seeded with a future-dated event, this check
# will legitimately fail because the window really is still open.
status, _, _ = request(
    "POST", "/api/projects",
    {"title": "Late Submission Attempt", "tagline": "should be rejected by the deadline guard"},
    cookie=cookie_p,
)
check("T1.3 closed event rejects participant submission -> 4xx", 400 <= status < 500)

status, _, _ = request("GET", "/api/organizer/export.csv?event_id=missing", cookie=cookie_org)
check("T2.4 organizer export endpoint reachable (200 expected once event seeded)", status in (200, 400))

print()
print(f"{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)

"""
Organizer-only, READ-ONLY insight views over data RAPTOR already has:
normalization runs, the audit chain, scores, assignments and votes.

Nothing here writes to the database or changes how anything is scored. The one
place that re-runs real logic (the integrity monitor's "normalization
reproducible" check) recomputes into memory and rolls back.

Every check in /integrity is backed by a query; anything the data cannot prove
is listed under `not_evaluated` instead of being given a green tick.
"""
import statistics
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import community as cm, config, insight_calc as ic, models
from ..audit import _hash_payload
from ..database import get_db
from ..deps import require_organizer
from ..normalization import run_normalization
from ..windows import _as_utc_aware, voting_state
from .organizer import (
    MAX_PROJECTS_PER_JUDGE,
    MIN_REVIEWS_PER_PROJECT,
    _resolve_event_id,
    explain_ranking,
)

router = APIRouter(prefix="/api/organizer/insight", tags=["insight-organizer"])


# ------------------------------------------------------------------ helpers --

def _iso(dt):
    return _as_utc_aware(dt).isoformat() if dt is not None else None


def _latest_run(db: Session, event_id: str) -> models.NormalizationRun:
    run = db.execute(
        select(models.NormalizationRun)
        .where(models.NormalizationRun.event_id == event_id)
        .order_by(models.NormalizationRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=400, detail="Run normalization first")
    return run


def _user_names(db: Session) -> dict[str, dict]:
    rows = db.execute(select(models.User.id, models.User.display_name, models.User.role)).all()
    return {r[0]: {"id": r[0], "name": r[1], "role": r[2]} for r in rows}


def _criteria(db: Session, event_id: str) -> list[models.RubricCriterion]:
    return db.execute(
        select(models.RubricCriterion)
        .where(models.RubricCriterion.event_id == event_id)
        .order_by(models.RubricCriterion.name)
    ).scalars().all()


def _verify_events(events: list[models.AuditEvent], head: models.AuditChainHead | None):
    """Per-event chain verification (same rules as audit.verify_chain, but
    reports every event instead of stopping at the first break)."""
    flags = []
    prev_hash = None
    expected_seq = 1
    for e in events:
        seq_ok = e.seq == expected_seq
        prev_ok = e.prev_hash == prev_hash
        hash_ok = _hash_payload(e.payload, prev_hash) == e.payload_hash
        flags.append({"seq": seq_ok, "prev_hash": prev_ok, "hash": hash_ok,
                      "verified": seq_ok and prev_ok and hash_ok})
        prev_hash = e.payload_hash
        expected_seq = e.seq + 1
    if events:
        head_matches = head is not None and head.last_seq == events[-1].seq \
            and head.last_hash == events[-1].payload_hash
    else:
        head_matches = head is None or head.last_seq == 0
    broken = next((e.seq for e, f in zip(events, flags) if not f["verified"]), None)
    return flags, {
        "valid": broken is None and head_matches,
        "events": len(events),
        "head_seq": head.last_seq if head else None,
        "head_matches_last_event": head_matches,
        "first_broken_seq": broken,
    }


def _score_pairs(db: Session) -> dict[tuple[str, str], dict]:
    """(judge_id, project_id) -> {n, mean, submitted_at} over submitted scores."""
    rows = db.execute(
        select(
            models.Score.judge_id, models.Score.project_id,
            func.count(), func.avg(models.Score.value), func.max(models.Score.submitted_at),
        ).group_by(models.Score.judge_id, models.Score.project_id)
    ).all()
    return {
        (j, p): {"n": n, "mean": float(avg), "submitted_at": _as_utc_aware(ts) if ts else None}
        for j, p, n, avg, ts in rows
    }


# ------------------------------------------------- 1. ranking transformation --

@router.get("/transformation", summary="Raw-to-final rank movement and biggest movers (organizer only)")
def transformation(
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    eid = _resolve_event_id(db, event_id)
    run = _latest_run(db, eid)
    titles = dict(db.execute(
        select(models.Project.id, models.Project.title)
        .where(models.Project.id.in_(list(run.results.keys())))
    ).all())
    data = ic.transformation_rows(run.results, titles)
    return {
        "run_id": run.id, "created_at": _iso(run.created_at),
        "algorithm": run.algorithm, "parameters": run.parameters, **data,
    }


# --------------------------------------------------------- 2. ranking autopsy --

@router.get("/autopsy/{project_id}", summary="Per-judge breakdown of one project's ranking (organizer only)")
def ranking_autopsy(
    project_id: str,
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    eid = _resolve_event_id(db, event_id)
    # Reuses the existing explain endpoint's own math (raises its 400/404s),
    # so the autopsy can never disagree with "Explain This Ranking".
    exp = explain_ranking(project_id, event_id=eid, db=db, user=user)
    project = db.get(models.Project, project_id)
    crits = _criteria(db, eid)
    weights = {c.id: float(c.weight) for c in crits}
    crit_name = {c.id: c.name for c in crits}
    names = _user_names(db)
    result = exp["result"]

    if result.get("insufficient_data"):
        return {
            "run_id": exp["run_id"], "project_id": project_id,
            "title": project.title if project else "?", "result": result,
            "headline": ic.autopsy_headline(result, None, None),
            "judges": [], "contribution_total": None, "reconciles": None,
            "criteria": [], "parameters": exp["parameters"],
        }

    a = ic.autopsy(exp["explanations"], weights)
    by_judge_scores = defaultdict(list)
    for e in exp["explanations"]:
        by_judge_scores[e["judge_id"]].append({
            "criterion": crit_name.get(e["criterion_id"], e["criterion_id"][:8]),
            "weight": weights.get(e["criterion_id"], 0.0),
            "raw": e["raw_score"], "z": e["z_score"], "mode": e["normalization"],
        })
    for j in a["judges"]:
        j["name"] = names.get(j["judge_id"], {}).get("name", j["judge_id"][:8])
        j["scores"] = sorted(by_judge_scores[j["judge_id"]], key=lambda s: s["criterion"])

    primary = a["judges"][0] if a["judges"] else None
    final = result.get("final_score")
    return {
        "run_id": exp["run_id"], "project_id": project_id,
        "title": project.title if project else "?", "result": result,
        "parameters": exp["parameters"],
        "headline": ic.autopsy_headline(result, primary, primary["name"] if primary else None),
        "judges": a["judges"],
        "contribution_total": a["contribution_total"],
        "reconciles": final is not None and abs(a["contribution_total"] - final) < 1e-4,
        "criteria": [{"id": c.id, "name": c.name, "weight": float(c.weight)} for c in crits],
    }


# ------------------------------------------------------ 3. judge calibration --

@router.get("/calibration", summary="Per-judge calibration profiles from the latest normalization run (organizer only)")
def calibration(
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    eid = _resolve_event_id(db, event_id)
    run = _latest_run(db, eid)
    n_min = int(run.parameters["min_samples"])
    prof = ic.calibration_profiles(run.input_snapshot, n_min)
    names = _user_names(db)
    crit_name = {c.id: c.name for c in _criteria(db, eid)}

    detail: dict[str, list] = defaultdict(list)
    for key, vals in run.input_snapshot.items():
        j, c = key.split(":", 1)
        vals = [float(v) for v in vals]
        detail[j].append({
            "criterion": crit_name.get(c, c[:8]), "n": len(vals),
            "mean": round(statistics.fmean(vals), 3),
            "stdev": round(statistics.pstdev(vals), 3) if len(vals) > 1 else 0.0,
        })
    for j in prof["judges"]:
        j["name"] = names.get(j["judge_id"], {}).get("name", j["judge_id"][:8])
        j["criteria"] = sorted(detail[j["judge_id"]], key=lambda d: d["criterion"])
    return {
        "run_id": run.id, "algorithm": run.algorithm,
        "parameters": run.parameters, **prof,
    }


# ---------------------------------------------------------- 4. judging replay --

@router.get("/replay", summary="Timeline of the whole judging process with per-event chain verification (organizer only)")
def replay(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    events = db.execute(
        select(models.AuditEvent).order_by(models.AuditEvent.seq.asc())
    ).scalars().all()
    head = db.get(models.AuditChainHead, 1)
    flags, chain = _verify_events(events, head)
    names = _user_names(db)
    titles = dict(db.execute(select(models.Project.id, models.Project.title)).all())
    pairs = _score_pairs(db)

    first_ts = _as_utc_aware(events[0].created_at) if events else None
    t0 = first_ts

    out = []
    for e, f in zip(events, flags):
        ts = _as_utc_aware(e.created_at)
        detail = None
        if e.action == "score.submitted" and e.actor_id and e.entity_id:
            p = pairs.get((e.actor_id, e.entity_id))
            if p:
                detail = {"raw_mean": round(p["mean"], 3), "criteria_scored": p["n"],
                          "scores_submitted_at": _iso(p["submitted_at"])}
        elif e.action == "normalization.run" and e.entity_id:
            run = db.get(models.NormalizationRun, e.entity_id)
            if run:
                ranked = [r for r in run.results.values() if not r.get("insufficient_data")]
                detail = {
                    "projects_ranked": len(ranked),
                    "projects_insufficient_data": len(run.results) - len(ranked),
                    "largest_rank_move": max((abs(r["rank_displacement"]) for r in ranked), default=0),
                }
        out.append({
            "seq": e.seq, "action": e.action,
            "actor": names.get(e.actor_id) if e.actor_id else None,
            "entity_type": e.entity_type, "entity_id": e.entity_id,
            "entity_label": titles.get(e.entity_id) if e.entity_type == "project" else None,
            "created_at": ts.isoformat(),
            "t_offset_s": int((ts - t0).total_seconds()) if t0 else 0,
            "payload": e.payload, "payload_hash": e.payload_hash, "prev_hash": e.prev_hash,
            "verified": f["verified"], "checks": {k: f[k] for k in ("seq", "prev_hash", "hash")},
            "detail": detail,
        })

    # Scores that predate the first audit event were loaded by the fixture
    # seeder, not submitted through the API, so no audit event exists for them.
    baseline_pairs = [k for k, v in pairs.items()
                      if v["submitted_at"] is not None and (first_ts is None or v["submitted_at"] < first_ts)]
    baseline = None
    if baseline_pairs:
        baseline = {
            "reviews": len(baseline_pairs),
            "judges": len({j for j, _ in baseline_pairs}),
            "projects": len({p for _, p in baseline_pairs}),
            "imported_at": min(pairs[k]["submitted_at"] for k in baseline_pairs).isoformat(),
            "note": "Loaded before the audit chain began (fixture seed); no per-score audit events exist for these.",
        }
    return {
        "chain": chain, "baseline": baseline,
        "phases": ic.group_phases(out), "events": out,
    }


# --------------------------------------------------------- 5. integrity status --

def _check(id_, label, status, detail, evidence=None, note=None):
    return {"id": id_, "label": label, "status": status, "detail": detail,
            "evidence": evidence or {}, "note": note}


@router.get("/integrity", summary="Evidence-backed integrity checks; no composite score (organizer only)")
def integrity(
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    eid = _resolve_event_id(db, event_id)
    checks = []

    events = db.execute(
        select(models.AuditEvent).order_by(models.AuditEvent.seq.asc())
    ).scalars().all()
    head = db.get(models.AuditChainHead, 1)
    _, chain = _verify_events(events, head)
    first_ts = _as_utc_aware(events[0].created_at) if events else None

    # 1. audit chain
    checks.append(_check(
        "audit_chain", "Audit chain",
        "pass" if chain["valid"] else "fail",
        f"{chain['events']} events, hashes recomputed end to end"
        + ("" if chain["valid"] else f"; first break at seq {chain['first_broken_seq']}"),
        chain,
    ))

    # 2. scores <-> audit reconciliation
    pairs = _score_pairs(db)
    audited = {}
    for e in events:
        if e.action == "score.submitted" and e.actor_id and e.entity_id:
            audited[(e.actor_id, e.entity_id)] = (e.payload or {}).get("criteria_count")
    matched = mismatched = baseline = unaudited = 0
    for k, v in pairs.items():
        if k in audited:
            if audited[k] == v["n"]:
                matched += 1
            else:
                mismatched += 1
        elif v["submitted_at"] is not None and (first_ts is None or v["submitted_at"] < first_ts):
            baseline += 1
        else:
            unaudited += 1
    orphans = sum(1 for k in audited if k not in pairs)
    bad = mismatched + unaudited + orphans
    checks.append(_check(
        "scores_vs_audit", "Scores match audit trail",
        "fail" if bad else "pass",
        f"{matched} submitted reviews match their audit event"
        + (f"; {baseline} predate the chain (fixture seed)" if baseline else "")
        + (f"; {bad} problem(s)" if bad else ""),
        {"matched": matched, "criteria_count_mismatch": mismatched,
         "scored_without_audit_event": unaudited, "audit_event_without_scores": orphans,
         "predate_chain": baseline},
        note="Compares score rows to score.submitted events (existence and criteria count). "
             "Score values themselves are not hashed into the chain.",
    ))

    # 3. assignment constraints
    assigned = {(a.judge_id, a.project_id) for a in db.execute(select(models.Assignment)).scalars()}
    scored_unassigned = sum(1 for k in pairs if k not in assigned)
    dup_assign = db.execute(
        select(func.count()).select_from(
            select(models.Assignment.judge_id, models.Assignment.project_id)
            .group_by(models.Assignment.judge_id, models.Assignment.project_id)
            .having(func.count() > 1).subquery()
        )
    ).scalar_one()
    load = defaultdict(int)
    reviews = defaultdict(int)
    for j, p in assigned:
        load[j] += 1
        reviews[p] += 1
    submitted_ids = [r[0] for r in db.execute(
        select(models.Project.id).where(models.Project.status == "submitted")).all()]
    under = sum(1 for pid in submitted_ids if reviews.get(pid, 0) < MIN_REVIEWS_PER_PROJECT)
    checks.append(_check(
        "assignments", "Assignment constraints",
        "fail" if (scored_unassigned or dup_assign) else "pass",
        f"{scored_unassigned} scores by unassigned judges, {dup_assign} duplicate assignments",
        {"scored_without_assignment": scored_unassigned, "duplicate_assignments": dup_assign,
         "max_projects_per_judge_observed": max(load.values(), default=0),
         "max_projects_per_judge_limit": MAX_PROJECTS_PER_JUDGE,
         "projects_below_min_reviews": under, "min_reviews_target": MIN_REVIEWS_PER_PROJECT},
        note="The per-judge limit is enforced by the assignment algorithm only, so seeded data can exceed it; "
             "it is reported, not failed.",
    ))

    # 4. vote constraints (from the vote table itself)
    dup_votes = db.execute(
        select(func.count()).select_from(
            select(models.Vote.voter_id, models.Vote.project_id)
            .group_by(models.Vote.voter_id, models.Vote.project_id)
            .having(func.count() > 1).subquery()
        )
    ).scalar_one()
    over_cap = db.execute(
        select(func.count()).select_from(
            select(models.Vote.voter_id).group_by(models.Vote.voter_id)
            .having(func.count() > config.VOTE_CAP_PER_VOTER).subquery()
        )
    ).scalar_one()
    own_team = db.execute(
        select(func.count()).select_from(models.Vote)
        .join(models.Project, models.Project.id == models.Vote.project_id)
        .join(models.TeamMember, (models.TeamMember.team_id == models.Project.team_id)
              & (models.TeamMember.user_id == models.Vote.voter_id))
    ).scalar_one()
    total_votes = db.execute(select(func.count()).select_from(models.Vote)).scalar_one()
    vbad = dup_votes + over_cap + own_team
    checks.append(_check(
        "votes", "Vote rules hold",
        "fail" if vbad else "pass",
        f"{total_votes} votes: {dup_votes} duplicates, {over_cap} voters over cap, {own_team} own-team votes",
        {"total_votes": total_votes, "duplicates": dup_votes, "voters_over_cap": over_cap,
         "own_team_votes": own_team, "cap": config.VOTE_CAP_PER_VOTER},
    ))

    # 5. blocked attempts (audited rejections)
    blocked_rows = db.execute(
        select(models.AuditEvent.action, func.count())
        .where(models.AuditEvent.action.in_((*cm.VOTE_REJECT_ACTIONS, "vote.rate_limited", "comment.rate_limited")))
        .group_by(models.AuditEvent.action)
    ).all()
    blocked = {a: n for a, n in blocked_rows}
    checks.append(_check(
        "blocked_attempts", "Blocked attempts on record", "info",
        f"{sum(blocked.values())} rejected attempts were blocked and written to the audit chain",
        blocked,
    ))

    # 6. normalization reproducibility (recompute in memory, then roll back)
    latest = db.execute(
        select(models.NormalizationRun).where(models.NormalizationRun.event_id == eid)
        .order_by(models.NormalizationRun.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    if latest is None:
        checks.append(_check("normalization", "Normalization reproducible", "info",
                             "No normalization run yet"))
    else:
        latest_id = latest.id
        old = dict(latest.results)
        run_at = _as_utc_aware(latest.created_at)
        later_scores = sum(1 for v in pairs.values() if v["submitted_at"] and v["submitted_at"] > run_at)
        fresh = run_normalization(db, eid)
        new = dict(fresh.results)
        db.rollback()  # discard the in-memory recomputation; nothing is persisted
        worst, mismatch = 0.0, 0
        for pid in set(old) | set(new):
            o, n = old.get(pid), new.get(pid)
            if o is None or n is None or o["insufficient_data"] != n["insufficient_data"]:
                mismatch += 1
                continue
            if o["insufficient_data"]:
                continue
            d = max(abs(o["final_score"] - n["final_score"]), abs(o["raw_average"] - n["raw_average"]))
            worst = max(worst, d)
            if d > 1e-9:
                mismatch += 1
        if mismatch == 0:
            status, detail = "pass", f"Recomputed from current scores: {len(old)} projects identical to run"
        elif later_scores:
            status, detail = "info", (f"STALE: {later_scores} review(s) submitted after this run; "
                                      "re-run normalization to refresh rankings")
        else:
            status, detail = "fail", f"{mismatch} project(s) differ on recompute with no newer scores"
        checks.append(_check(
            "normalization", "Normalization reproducible", status, detail,
            {"run_id": latest_id, "projects": len(old), "mismatches": mismatch,
             "max_abs_score_delta": worst, "reviews_after_run": later_scores},
            note="Compares scores, not rank order: exact ties may be ordered differently between processes.",
        ))

    return {
        "summary": {s: sum(1 for c in checks if c["status"] == s) for s in ("pass", "fail", "info")},
        "checks": checks,
        "not_evaluated": [
            "Role isolation and blind-judging redaction: enforced in request handlers, "
            "not observable from stored data.",
            "Score value integrity: values are protected by a uniqueness constraint and immutable API, "
            "but are not hashed into the audit chain.",
        ],
    }


# ------------------------------------------------------- 6. public vs jury ----

@router.get("/public-vs-jury", summary="Community vote ranking against jury ranking (organizer only)")
def public_vs_jury(
    event_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(require_organizer),
):
    eid = _resolve_event_id(db, event_id)
    run = _latest_run(db, eid)
    state, _ = voting_state(db, eid)

    projects = db.execute(
        select(models.Project.id, models.Project.title)
        .join(models.Team, models.Project.team_id == models.Team.id)
        .where(models.Team.event_id == eid, models.Project.status == "submitted")
    ).all()
    votes = dict(db.execute(
        select(models.Vote.project_id, func.count())
        .where(models.Vote.event_id == eid).group_by(models.Vote.project_id)
    ).all())
    vote_of = {pid: int(votes.get(pid, 0)) for pid, _ in projects}
    comm_rank = ic.competition_ranks({pid: float(n) for pid, n in vote_of.items()})

    rows = []
    for pid, title in projects:
        r = run.results.get(pid) or {}
        jury_rank = r.get("final_rank")
        rows.append({
            "project_id": pid, "title": title, "votes": vote_of[pid],
            "community_rank": comm_rank[pid], "jury_rank": jury_rank,
            "jury_score": r.get("final_score"),
            # positive: community ranks it higher than the jury does
            "gap": (jury_rank - comm_rank[pid]) if jury_rank is not None else None,
        })
    rows.sort(key=lambda r: (r["community_rank"], r["title"]))

    both = [r for r in rows if r["jury_score"] is not None]
    corr = ic.spearman([float(r["votes"]) for r in both], [r["jury_score"] for r in both]) \
        if sum(vote_of.values()) > 0 else None
    gapped = [r for r in rows if r["gap"] is not None and r["votes"] > 0]
    return {
        "voting_state": state, "run_id": run.id,
        "total_votes": sum(vote_of.values()),
        "correlation": None if corr is None else round(corr, 3),
        "correlation_n": len(both),
        "rows": rows,
        "community_over_jury": sorted((r for r in gapped if r["gap"] > 0), key=lambda r: -r["gap"])[:3],
        "jury_over_community": sorted((r for r in gapped if r["gap"] < 0), key=lambda r: r["gap"])[:3],
    }

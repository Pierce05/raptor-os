"""
Pure calculation helpers for the organizer "insight" views (see
routers/insight.py). No database, FastAPI or SQLAlchemy imports on purpose:
everything here takes plain dicts/lists, so it can be unit-tested (and
reasoned about) without the stack.

Nothing in this module changes how scores are normalized. It only re-reads
numbers the normalization run already produced and reports them in a more
human shape.
"""
from __future__ import annotations

import statistics
from typing import Iterable

# A judge whose mean sits this many panel-standard-deviations away from the
# panel mean is labelled STRICT / GENEROUS. Returned to the client so the UI
# can show the rule instead of hiding it.
STRICTNESS_THRESHOLD = 0.25


# ---------------------------------------------------------------- ranking ----

def competition_ranks(values: dict[str, float]) -> dict[str, int]:
    """Higher value = better. Ties share the best rank (1,2,2,4)."""
    ordered = sorted(values.items(), key=lambda kv: -kv[1])
    ranks: dict[str, int] = {}
    prev_val = None
    prev_rank = 0
    for i, (k, v) in enumerate(ordered, start=1):
        if prev_val is not None and v == prev_val:
            ranks[k] = prev_rank
        else:
            ranks[k] = i
            prev_rank, prev_val = i, v
    return ranks


def _average_ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation using average ranks for ties.
    None when there are < 3 pairs or either side has no variance."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _average_ranks(xs), _average_ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return None if den == 0 else num / den


def _winner(ranked: list[dict]) -> dict | None:
    if not ranked:
        return None
    final = ranked[0]
    raw = next((r for r in ranked if r["raw_rank"] == 1), None)
    return {
        "final": final["title"], "raw": raw["title"] if raw else None,
        "changed": raw is not None and raw["project_id"] != final["project_id"],
    }


def transformation_rows(results: dict[str, dict], titles: dict[str, str]) -> dict:
    """Raw -> final movement table + biggest movers, from a normalization run's
    `results` dict. Projects without data are listed separately, never ranked."""
    ranked, unranked = [], []
    for pid, r in results.items():
        row = {"project_id": pid, "title": titles.get(pid, "?"), **r}
        (unranked if r.get("insufficient_data") else ranked).append(row)
    ranked.sort(key=lambda r: r["final_rank"])
    movers = [r for r in ranked if r["rank_displacement"]]
    up = sorted((r for r in movers if r["rank_displacement"] > 0),
                key=lambda r: -r["rank_displacement"])[:5]
    down = sorted((r for r in movers if r["rank_displacement"] < 0),
                  key=lambda r: r["rank_displacement"])[:5]
    return {
        "rows": ranked,
        "insufficient_data": unranked,
        "biggest_up": up,
        "biggest_down": down,
        "unchanged": sum(1 for r in ranked if r["rank_displacement"] == 0),
        "moved": len(movers),
        "winner": _winner(ranked),
    }


# ---------------------------------------------------------------- autopsy ----

def autopsy(explanations: list[dict], weights: dict[str, float]) -> dict:
    """
    Decompose one project's final score into per-judge contributions.

    final_score = sum_c  w_c * mean_j(z_jc)
                = sum_j  sum_c  w_c * z_jc / n_c        (n_c = judges scoring c)

    so each judge's `contribution` is exact and the contributions add up to the
    final score (`reconciles` reports whether they do, to 1e-4 -- the explain
    endpoint rounds z to 6 places).

    `calibration_shift` is how much of that contribution is due to judge-specific
    calibration: the same score standardised against the judge's own scale
    (what normalization did) minus the same score standardised against the
    whole panel's scale (what it would have been for an "average" judge).
    Positive = calibration helped this project.
    """
    n_by_crit: dict[str, int] = {}
    for e in explanations:
        n_by_crit[e["criterion_id"]] = n_by_crit.get(e["criterion_id"], 0) + 1

    judges: dict[str, dict] = {}
    for e in explanations:
        c, j = e["criterion_id"], e["judge_id"]
        w = weights.get(c, 0.0)
        n_c = n_by_crit[c]
        g_sd = e["global_stdev"] or 1.0
        z_panel = (e["raw_score"] - e["global_mean"]) / g_sd
        entry = judges.setdefault(j, {
            "judge_id": j, "contribution": 0.0, "calibration_shift": 0.0,
            "raw_scores": [], "bias": [], "modes": set(),
        })
        entry["contribution"] += w * e["z_score"] / n_c
        entry["calibration_shift"] += w * (e["z_score"] - z_panel) / n_c
        entry["raw_scores"].append(e["raw_score"])
        entry["bias"].append((e["judge_mean"] - e["global_mean"]) / g_sd)
        entry["modes"].add(e["normalization"])

    out = []
    for entry in judges.values():
        out.append({
            "judge_id": entry["judge_id"],
            "contribution": round(entry["contribution"], 6),
            "calibration_shift": round(entry["calibration_shift"], 6),
            "raw_mean": round(statistics.fmean(entry["raw_scores"]), 4),
            "strictness": round(statistics.fmean(entry["bias"]), 4),
            "modes": sorted(entry["modes"]),
        })
    out.sort(key=lambda x: -abs(x["calibration_shift"]))
    total = sum(x["contribution"] for x in out)
    return {"judges": out, "contribution_total": round(total, 6)}


def autopsy_headline(result: dict, primary: dict | None, primary_name: str | None) -> list[str]:
    """Plain-language lines. Deliberately says 'largest calibration adjustment',
    not 'cause': a project's rank also moves because of how OTHER projects were
    adjusted, which this per-project view cannot attribute."""
    lines = []
    raw, fin, disp = result.get("raw_rank"), result.get("final_rank"), result.get("rank_displacement")
    if raw is None or fin is None:
        return ["This project has no submitted scores yet, so it is not ranked."]
    if disp == 0:
        lines.append(f"Raw rank #{raw} and final rank #{fin}: normalization did not move this project.")
    else:
        word = "up" if disp > 0 else "down"
        lines.append(f"Raw rank #{raw} -> final rank #{fin} ({word} {abs(disp)}).")
    if primary and abs(primary["calibration_shift"]) >= 0.01:
        harsher = primary["strictness"] < 0
        lines.append(
            f"Largest calibration adjustment: {primary_name or 'a judge'} scores "
            f"{'harsher' if harsher else 'more generously'} than the panel "
            f"(strictness {primary['strictness']:+.2f} panel-SD), so normalization "
            f"{'raised' if primary['calibration_shift'] > 0 else 'lowered'} this project's "
            f"weighted score by {abs(primary['calibration_shift']):.3f}."
        )
    else:
        lines.append("No single judge's calibration moved this project's score materially.")
    return lines


# ------------------------------------------------------------ calibration ----

def calibration_profiles(snapshot: dict[str, list[float]], n_min: int) -> dict:
    """
    Per-judge calibration profile from a normalization run's input_snapshot
    (keys are "judge_id:criterion_id", values are that judge's raw scores).

    strictness = mean over criteria of (judge mean - panel mean) / panel SD,
    i.e. how many panel standard deviations above/below the panel this judge
    typically scores. Panel stats are computed exactly as normalization.py does
    (pooled over every score for the criterion).

    confidence mirrors what normalization actually did for this judge:
      n >= n_min  -> HIGH   (judge's own mean/SD used)
      2 <= n < n_min -> MEDIUM (SD shrunk toward the panel)
      n <= 1      -> LOW    (panel mean/SD used; judge not calibrated at all)
    where n is the judge's smallest per-criterion sample count.
    """
    by_crit: dict[str, list[float]] = {}
    per_judge: dict[str, dict[str, list[float]]] = {}
    for key, vals in snapshot.items():
        j, c = key.split(":", 1)
        vals = [float(v) for v in vals]
        by_crit.setdefault(c, []).extend(vals)
        per_judge.setdefault(j, {})[c] = vals

    g = {
        c: (statistics.fmean(v), (statistics.pstdev(v) if len(v) > 1 else 1.0) or 1.0)
        for c, v in by_crit.items()
    }
    panel_all = [x for v in by_crit.values() for x in v]

    profiles = []
    for j, crits in per_judge.items():
        bias, spread = [], []
        n_reviews = 0
        n_floor = None
        all_vals: list[float] = []
        for c, vals in crits.items():
            gm, gs = g[c]
            bias.append((statistics.fmean(vals) - gm) / gs)
            if len(vals) > 1:
                spread.append(statistics.pstdev(vals) / gs)
            n_reviews = max(n_reviews, len(vals))
            n_floor = len(vals) if n_floor is None else min(n_floor, len(vals))
            all_vals.extend(vals)
        strictness = statistics.fmean(bias)
        if n_floor is not None and n_floor >= n_min:
            conf, mode = "HIGH", "judge"
        elif n_floor is not None and n_floor >= 2:
            conf, mode = "MEDIUM", "shrunk"
        else:
            conf, mode = "LOW", "global"
        if strictness <= -STRICTNESS_THRESHOLD:
            label = "STRICT"
        elif strictness >= STRICTNESS_THRESHOLD:
            label = "GENEROUS"
        else:
            label = "NEUTRAL"
        profiles.append({
            "judge_id": j,
            "reviews": n_reviews,
            "raw_mean": round(statistics.fmean(all_vals), 4),
            "raw_stdev": round(statistics.pstdev(all_vals), 4) if len(all_vals) > 1 else 0.0,
            "strictness": round(strictness, 4),
            "spread_ratio": round(statistics.fmean(spread), 4) if spread else None,
            "label": label,
            "confidence": conf,
            "normalization_mode": mode,
        })
    profiles.sort(key=lambda p: p["strictness"])
    return {
        "panel_mean": round(statistics.fmean(panel_all), 4) if panel_all else None,
        "panel_stdev": round(statistics.pstdev(panel_all), 4) if len(panel_all) > 1 else None,
        "strictness_threshold": STRICTNESS_THRESHOLD,
        "min_samples": n_min,
        "judges": profiles,
    }


# ----------------------------------------------------------------- replay ----

def group_phases(events: Iterable[dict]) -> list[dict]:
    """Collapse consecutive events with the same action into one phase, so 130
    score submissions read as one 'SCORES SUBMITTED x130' block."""
    phases: list[dict] = []
    for e in events:
        if phases and phases[-1]["action"] == e["action"]:
            p = phases[-1]
            p["count"] += 1
            p["last_seq"] = e["seq"]
            p["ended_at"] = e["created_at"]
        else:
            phases.append({
                "action": e["action"], "count": 1,
                "first_seq": e["seq"], "last_seq": e["seq"],
                "started_at": e["created_at"], "ended_at": e["created_at"],
            })
    return phases

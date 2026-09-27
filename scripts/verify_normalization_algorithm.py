"""
Scratch verification script (not part of the app). SQLAlchemy isn't
installable in this sandbox, so this can't import app/normalization.py
directly (it needs a live Session). Instead, the computation body of
run_normalization() is copied verbatim below -- everything after the
two DB queries -- with the query results replaced by hand-built
synthetic data. This tests the actual algorithm, not a reimplementation
of it from memory.

Scenario: 3 projects in the event. Two judges score two of them
normally; the third has zero scores at all (should show up flagged).
"""
import statistics
from collections import defaultdict

k = 5.0          # config.NORMALIZATION_SHRINKAGE_K default
n_min = 5        # config.NORMALIZATION_MIN_SAMPLES default

# ---- synthetic stand-ins for the two DB queries in run_normalization ----
all_project_ids = {"proj-A", "proj-B", "proj-ZERO"}
weight_by_criterion = {"crit-innovation": 0.5, "crit-technical": 0.5}

# (project_id, judge_id, criterion_id) -> raw score, standing in for
# `all_scores` rows. proj-ZERO deliberately has none.
raw_rows = [
    ("proj-A", "judge-1", "crit-innovation", 4.0),
    ("proj-A", "judge-1", "crit-technical", 5.0),
    ("proj-A", "judge-2", "crit-innovation", 3.0),
    ("proj-A", "judge-2", "crit-technical", 3.0),
    ("proj-B", "judge-1", "crit-innovation", 2.0),
    ("proj-B", "judge-1", "crit-technical", 2.0),
    ("proj-B", "judge-2", "crit-innovation", 4.0),
    ("proj-B", "judge-2", "crit-technical", 4.0),
]

# ---- everything below is copied verbatim from app/normalization.py ----
# (variable names/comments match; only the two query results above feed
# in instead of `db.execute(select(...))`.)

by_judge_criterion: dict[tuple[str, str], list[float]] = defaultdict(list)
by_criterion_global: dict[str, list[float]] = defaultdict(list)
by_project_judge_criterion: dict[tuple[str, str, str], float] = {}

for (project_id, judge_id, criterion_id, v) in raw_rows:
    by_judge_criterion[(judge_id, criterion_id)].append(v)
    by_criterion_global[criterion_id].append(v)
    by_project_judge_criterion[(project_id, judge_id, criterion_id)] = v


def _judge_stats(scores_by_judge_criterion):
    stats = {}
    for key, values in scores_by_judge_criterion.items():
        n = len(values)
        mean = statistics.fmean(values) if n else 0.0
        stdev = statistics.pstdev(values) if n > 1 else 0.0
        stats[key] = {"n": n, "mean": mean, "stdev": stdev}
    return stats


judge_stats = _judge_stats(by_judge_criterion)
global_stats = {
    c_id: {
        "mean": statistics.fmean(vals) if vals else 0.0,
        "stdev": statistics.pstdev(vals) if len(vals) > 1 else 1.0,
    }
    for c_id, vals in by_criterion_global.items()
}


def adjusted_sigma(judge_id, criterion_id):
    st = judge_stats.get((judge_id, criterion_id), {"n": 0, "mean": 0.0, "stdev": 0.0})
    g = global_stats.get(criterion_id, {"mean": 0.0, "stdev": 1.0})
    n = st["n"]
    if n <= 1:
        return g["mean"], (g["stdev"] or 1.0)
    sigma_adj = (n * st["stdev"] + k * g["stdev"]) / (n + k)
    if n < n_min:
        return st["mean"], (sigma_adj or 1.0)
    return st["mean"], (st["stdev"] or sigma_adj or 1.0)


scored_project_ids = {p for (p, _, _) in by_project_judge_criterion} & all_project_ids
unscored_project_ids = all_project_ids - scored_project_ids

z_by_project_criterion: dict[tuple[str, str], list[float]] = defaultdict(list)

for (project_id, judge_id, criterion_id), raw in by_project_judge_criterion.items():
    if project_id not in scored_project_ids:
        continue
    mu, sigma = adjusted_sigma(judge_id, criterion_id)
    z = (raw - mu) / sigma if sigma else 0.0
    z_by_project_criterion[(project_id, criterion_id)].append(z)

raw_avg_by_project: dict[str, float] = defaultdict(float)
raw_counts: dict[str, int] = defaultdict(int)
final_by_project: dict[str, float] = {}

for project_id in scored_project_ids:
    final_score = 0.0
    for criterion_id, weight in weight_by_criterion.items():
        zs = z_by_project_criterion.get((project_id, criterion_id), [])
        mean_z = statistics.fmean(zs) if zs else 0.0
        final_score += weight * mean_z
    final_by_project[project_id] = final_score

    for (p, j, c), raw in by_project_judge_criterion.items():
        if p == project_id:
            raw_avg_by_project[project_id] += raw
            raw_counts[project_id] += 1

raw_rank_input = {
    p: (raw_avg_by_project[p] / raw_counts[p] if raw_counts[p] else 0.0)
    for p in scored_project_ids
}

raw_ranked = sorted(scored_project_ids, key=lambda p: raw_rank_input[p], reverse=True)
raw_rank = {p: i + 1 for i, p in enumerate(raw_ranked)}

final_ranked = sorted(scored_project_ids, key=lambda p: final_by_project[p], reverse=True)
final_rank = {p: i + 1 for i, p in enumerate(final_ranked)}

results = {
    p: {
        "raw_average": raw_rank_input[p],
        "final_score": final_by_project[p],
        "raw_rank": raw_rank[p],
        "final_rank": final_rank[p],
        "rank_displacement": raw_rank[p] - final_rank[p],
        "insufficient_data": False,
    }
    for p in scored_project_ids
}
results.update({
    p: {
        "raw_average": None,
        "final_score": None,
        "raw_rank": None,
        "final_rank": None,
        "rank_displacement": None,
        "insufficient_data": True,
    }
    for p in unscored_project_ids
})

# ---- assertions (this is the actual test) ----
print("results:")
for pid, r in sorted(results.items()):
    print(f"  {pid}: {r}")

assert set(results.keys()) == all_project_ids, "every project must appear in results"
assert results["proj-ZERO"]["insufficient_data"] is True
assert results["proj-ZERO"]["final_score"] is None
assert results["proj-ZERO"]["final_rank"] is None
assert results["proj-A"]["insufficient_data"] is False
assert results["proj-B"]["insufficient_data"] is False
assert {results["proj-A"]["final_rank"], results["proj-B"]["final_rank"]} == {1, 2}, \
    "ranks should be computed only among the two scored projects, as 1 and 2"

print()
print("ALL ASSERTIONS PASSED: zero-score project appears, flagged, with null rank fields;")
print("scored projects get real ranks computed only among themselves.")

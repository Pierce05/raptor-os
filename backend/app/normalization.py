"""
Regularized z-score normalization with shrinkage for sparse judges.
See JUDGING.md for the full write-up and worked example.

We deliberately do NOT claim this produces an "objectively fair" ranking.
It corrects for differences in each judge's scoring scale under the
stated assumption that a judge's scores approximate a stable
mean/variance across the projects they reviewed. It does not correct
for genuine disagreement about quality.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, config


def _judge_stats(scores_by_judge_criterion: dict) -> dict:
    """mean/stdev/n per (judge_id, criterion_id)."""
    stats = {}
    for key, values in scores_by_judge_criterion.items():
        n = len(values)
        mean = statistics.fmean(values) if n else 0.0
        stdev = statistics.pstdev(values) if n > 1 else 0.0
        stats[key] = {"n": n, "mean": mean, "stdev": stdev}
    return stats


def run_normalization(db: Session, event_id: str) -> models.NormalizationRun:
    criteria = db.execute(
        select(models.RubricCriterion).where(models.RubricCriterion.event_id == event_id)
    ).scalars().all()
    weight_by_criterion = {c.id: float(c.weight) for c in criteria}

    # Every SUBMITTED project for this event must show up in the run's
    # results, even one that no judge has scored yet -- silently
    # dropping zero-review projects would make the ranking/CSV/"Explain
    # This Ranking" views quietly lie about how many projects exist.
    all_event_projects = db.execute(
        select(models.Project)
        .join(models.Team, models.Project.team_id == models.Team.id)
        .where(models.Team.event_id == event_id, models.Project.status == "submitted")
    ).scalars().all()
    all_project_ids = {p.id for p in all_event_projects}

    # NOTE: pulls all Score rows regardless of event. This assumes a
    # single-event-per-deployment model (documented in THREAT-MODEL.md).
    # A multi-event deployment would need to join through
    # project -> team -> event and filter here.
    all_scores = db.execute(select(models.Score)).scalars().all()

    # group raw values by (judge, criterion) to compute per-judge scale,
    # and separately by criterion (global) for the shrinkage target
    by_judge_criterion: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_criterion_global: dict[str, list[float]] = defaultdict(list)
    by_project_judge_criterion: dict[tuple[str, str, str], float] = {}

    for s in all_scores:
        v = float(s.value)
        by_judge_criterion[(s.judge_id, s.criterion_id)].append(v)
        by_criterion_global[s.criterion_id].append(v)
        by_project_judge_criterion[(s.project_id, s.judge_id, s.criterion_id)] = v

    judge_stats = _judge_stats(by_judge_criterion)
    global_stats = {
        c_id: {
            "mean": statistics.fmean(vals) if vals else 0.0,
            "stdev": statistics.pstdev(vals) if len(vals) > 1 else 1.0,
        }
        for c_id, vals in by_criterion_global.items()
    }

    k = config.NORMALIZATION_SHRINKAGE_K
    n_min = config.NORMALIZATION_MIN_SAMPLES

    def adjusted_sigma(judge_id: str, criterion_id: str) -> tuple[float, float]:
        st = judge_stats.get((judge_id, criterion_id), {"n": 0, "mean": 0.0, "stdev": 0.0})
        g = global_stats.get(criterion_id, {"mean": 0.0, "stdev": 1.0})
        n = st["n"]
        if n <= 1:
            return g["mean"], (g["stdev"] or 1.0)
        sigma_adj = (n * st["stdev"] + k * g["stdev"]) / (n + k)
        if n < n_min:
            return st["mean"], (sigma_adj or 1.0)
        return st["mean"], (st["stdev"] or sigma_adj or 1.0)

    # per-project per-criterion mean z-score across assigned judges.
    # scored_project_ids is a SUBSET of all_project_ids -- only projects
    # that actually have at least one submitted score. Projects with
    # zero reviews are handled separately below so they still appear in
    # the run's results, flagged rather than silently dropped.
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

    # Ranks are computed only among projects with real data -- ranking a
    # zero-review project against scored ones would be meaningless, not
    # just incomplete.
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

    run = models.NormalizationRun(
        event_id=event_id,
        algorithm="regularized-z-v1",
        parameters={"shrinkage_k": k, "min_samples": n_min},
        input_snapshot={
            f"{j}:{c}": vals for (j, c), vals in by_judge_criterion.items()
        },
        results=results,
    )
    db.add(run)
    return run

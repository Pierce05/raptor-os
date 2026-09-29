"""Pure-math checks for app/insight_calc.py (no database needed)."""
import statistics

from app import insight_calc as ic


def test_competition_ranks_ties_share_best_rank():
    assert ic.competition_ranks({"a": 3, "b": 2, "c": 2, "d": 1}) == {"a": 1, "b": 2, "c": 2, "d": 4}


def test_spearman_perfect_inverse_and_degenerate():
    assert ic.spearman([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert ic.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == -1.0
    assert ic.spearman([1, 1, 1], [1, 2, 3]) is None
    assert ic.spearman([1, 2], [1, 2]) is None


def test_autopsy_contributions_sum_to_final_score():
    weights = {"c1": 0.5, "c2": 0.5}
    scores = {
        ("j1", "c1"): [5, 4, 3, 2, 5], ("j1", "c2"): [4, 4, 2, 3, 5],
        ("j2", "c1"): [2, 1, 3, 2, 1], ("j2", "c2"): [1, 2, 2, 3, 1],
    }
    panel = {c: [x for (j, cc), v in scores.items() if cc == c for x in v] for c in weights}
    expl = []
    for (j, c), v in scores.items():
        raw = v[0]
        expl.append({
            "judge_id": j, "criterion_id": c, "raw_score": raw,
            "judge_mean": statistics.fmean(v), "global_mean": statistics.fmean(panel[c]),
            "global_stdev": statistics.pstdev(panel[c]),
            "z_score": (raw - statistics.fmean(v)) / statistics.pstdev(v), "normalization": "judge",
        })
    final = sum(
        w * statistics.fmean([e["z_score"] for e in expl if e["criterion_id"] == c])
        for c, w in weights.items()
    )
    out = ic.autopsy(expl, weights)
    assert abs(out["contribution_total"] - final) < 1e-4


def test_calibration_labels_and_confidence():
    snap = {
        "harsh:c1": [1, 2, 1, 2, 1, 2], "mid:c1": [3, 3, 4, 3, 3, 4],
        "kind:c1": [5, 5, 4, 5, 5, 4], "sparse:c1": [5],
    }
    prof = {j["judge_id"]: j for j in ic.calibration_profiles(snap, 5)["judges"]}
    assert prof["harsh"]["label"] == "STRICT" and prof["harsh"]["confidence"] == "HIGH"
    assert prof["kind"]["label"] == "GENEROUS"
    assert prof["sparse"]["confidence"] == "LOW" and prof["sparse"]["normalization_mode"] == "global"


def test_transformation_winner_and_unranked():
    ok = {"insufficient_data": False, "raw_average": 4.0, "final_score": 1.0}
    res = {
        "p1": {**ok, "raw_rank": 2, "final_rank": 1, "rank_displacement": 1},
        "p2": {**ok, "raw_rank": 1, "final_rank": 2, "rank_displacement": -1},
        "p3": {"insufficient_data": True, "raw_average": None, "final_score": None,
               "raw_rank": None, "final_rank": None, "rank_displacement": None},
    }
    t = ic.transformation_rows(res, {"p1": "A", "p2": "B", "p3": "C"})
    assert t["winner"] == {"final": "A", "raw": "B", "changed": True}
    assert [r["project_id"] for r in t["insufficient_data"]] == ["p3"]
    assert t["moved"] == 2


def test_group_phases_collapses_consecutive_actions():
    ev = [{"action": "a", "seq": 1, "created_at": "t1"}, {"action": "a", "seq": 2, "created_at": "t2"},
          {"action": "b", "seq": 3, "created_at": "t3"}]
    ph = ic.group_phases(ev)
    assert [(p["action"], p["count"]) for p in ph] == [("a", 2), ("b", 1)]

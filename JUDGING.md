# Judging: normalization and explainability

## What problem this solves

Two judges can have identical *taste* but different *scales* — one
consistently gives 4s and 5s, another consistently gives 2s and 3s.
Averaging raw scores lets a judge's personal scale distort a project's
rank more than the judge's actual opinion of quality does.

## What this does NOT claim

We do not claim the algorithm below produces an "objectively fair"
ranking. It corrects for differences in scoring *scale* under a stated
assumption; it does not and cannot correct for genuine disagreement
about quality between judges.

## Algorithm: regularized z-score with shrinkage ("regularized-z-v1")

For judge `j` scoring project `p` on criterion `c`, with raw score `r`:

**1. Per-judge, per-criterion z-score**

```
z(j, p, c) = (r(j, p, c) - mean_j) / stdev_j
```

`mean_j`, `stdev_j` are computed across all scores judge `j` gave for
that criterion.

**2. Shrinkage for sparse judges**

If a judge has fewer than `MIN_SAMPLES` (default 5) scores for a
criterion, their own `stdev_j` isn't a reliable estimate of their
scale, so it's blended toward the criterion's global stdev:

```
stdev_adj = (n * stdev_j + k * stdev_global) / (n + k)
```

`k` (default 5) controls how aggressively we shrink. If a judge has 0
or 1 scores, `stdev_j` is undefined — we fall back entirely to the
global mean/stdev rather than dividing by zero.

**3. Weighted aggregation**

```
final(p) = sum over criteria c of: weight(c) * mean over judges of z(j, p, c)
```

**4. Ranking**

Projects are ranked by `final(p)` descending. We also compute
`raw_rank` (rank by unweighted raw average) so "rank displacement"
(`raw_rank - final_rank`) can be shown directly — this is the number
"Explain This Ranking" surfaces to show how much normalization moved a
project.

## Worked example

Judge A scores: 4, 4, 5, 4, 5 → mean 4.4, stdev ≈ 0.49
Judge B scores: 2, 3, 3, 4, 2 → mean 2.8, stdev ≈ 0.75

A project scored 4 by Judge A: `z = (4 - 4.4) / 0.49 ≈ -0.82`
A project scored 4 by Judge B: `z = (4 - 2.8) / 0.75 ≈ +1.60`

The same raw score of 4 lands very differently once each judge's own
scale is accounted for — Judge B's 4 was actually their highest score
and gets weighted accordingly.

## Immutable, versioned runs

Every run creates a new `NormalizationRun` row with a full snapshot of
inputs, parameters, and results. Runs are never overwritten, so any
past ranking remains inspectable and explainable — if the ranking
changes between Run #3 and Run #4, you can always see exactly why
(usually: more scores came in, or the parameters changed).

## Zero-review projects

A submitted project with no scores at all is still included in every
`NormalizationRun.results`, `/rankings`, and CSV export — flagged
`"insufficient_data": true` with null score/rank fields, rather than
being silently dropped. Ranks are computed only among projects that do
have scores (ranking a zero-review project against scored ones would
be meaningless, not just incomplete); flagged projects sort to the end
of `/rankings` and the CSV export instead of raising or vanishing.

## Known limitations

- Shrinkage parameters (`k = 5`, `MIN_SAMPLES = 5`) are reasonable
  defaults for ~40 projects / ~10 judges, not tuned against real data.
- The model assumes each judge's per-criterion scores approximate a
  stable distribution across the projects they reviewed; a judge who
  scores very few projects, or whose taste genuinely varies a lot by
  project, will be shrunk more aggressively toward the global scale.

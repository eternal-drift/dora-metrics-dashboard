# Engineering Health Scorecard

A single-page rollup meant to answer "is engineering healthy?" in one
glance, with a defined status rule per metric rather than a subjective
color. This is what `docs/vp-dashboard.md` summarizes in prose; this is the
mechanical scoring behind it.

## Status rule

Each metric gets a trend direction (comparing the trailing 4 weeks to the
prior 4 weeks) and a threshold band. Status is **not** vibes-based — it's a
fixed rule per metric, listed below, so the scorecard produces the same
color for the same data every time.

| Metric | 🟢 Green | 🟡 Yellow | 🔴 Red | Rule basis |
|---|---|---|---|---|
| PR cycle time (median) | < 24h | 24–48h | > 48h | Industry elite/high band per DORA; tunable in `dora/config.py` |
| Deployment frequency | ≥ weekly | biweekly–monthly | < monthly | DORA "high performer" band |
| Change failure rate | < 15% | 15–30% | > 30% | DORA elite/high band |
| Lead time for changes | < 48h | 2–7 days | > 7 days | DORA high band |
| MTTR | < 4h | 4–24h | > 24h | DORA elite/high band |
| WIP (per active engineer) | < 2 | 2–4 | > 4 | Common flow-management guidance; a proxy, see [metrics.md](metrics.md) caveat |
| Throughput trend | improving ≥5%/period | flat ±5% | declining >5% | Trailing-4-vs-prior-4-period comparison |

## Sample scorecard (from seeded demo data, week 26)

| Metric | Value | Status | Trend |
|---|---|---|---|
| PR cycle time (median) | 19.7h | 🟢 | ↓ improving |
| Change failure rate | ~5% | 🟢 | ↓ improving |
| Throughput | 35 issues/mo | 🟢 | ↑ improving |
| Deployment frequency | ~weekly | 🟢 | → stable |
| MTTR | not computed — no incident issues seeded in this run | ⚪ no data | — |
| Lead time for changes | requires release cadence check | 🟡 | depends on release batching |
| WIP per engineer | ~1–2 (5 engineers, trickle backlog) | 🟢 | → stable |

## What this scorecard deliberately does not do

- It does not aggregate into a single "engineering health score." A single
  number invites exactly the kind of gaming and false precision this
  system's caveats (see [metrics.md](metrics.md)) exist to prevent — a red
  MTTR and a green deployment frequency are not fungible.
- It does not compare teams/repos against each other without controlling
  for team size, repo age, and codebase type. Cross-team comparison on raw
  thresholds produces exactly the kind of metric misuse a "how did you
  avoid metrics becoming a stick" interview question is testing for.
- Status for a metric marked with a proxy caveat in [metrics.md](metrics.md)
  should always be read next to that caveat — "red" on change failure rate
  could mean real production instability, or it could mean the hotfix
  keyword heuristic is over-matching this repo's PR title conventions.

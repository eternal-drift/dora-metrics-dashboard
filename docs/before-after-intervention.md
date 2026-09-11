# Simulated Before/After Intervention

This walks through the improvement story encoded in `scripts/seed_demo_data.py`
and reproducible by anyone who runs `python scripts/seed_demo_data.py acme/widgets`
followed by `python cli.py` / `streamlit run dashboard.py` against the
resulting `dora.db`. Every number below was pulled from that seeded dataset
by querying `dora.metrics`, not hand-written — see the query at the bottom.

## The intervention (narrative)

A team of 5 engineers spends the first stretch of a 26-week window with:
slow PR cycle times, a meaningful share of releases needing a same-day
hotfix, and modest throughput. Over the window they adopt tighter PR
scoping, faster review SLAs, and better release hygiene — the kind of
changes a metrics-driven EM actually drives, not a tooling swap. The
synthetic generator encodes this as a linear "maturity" trend from week 0
to week 25 (`maturity = week / 26`), which is deliberately conservative:
real interventions rarely improve this smoothly, but a smooth trend makes
the before/after comparison legible without cherry-picking weeks.

## Before → After (first quartile of PRs vs. last quartile, by merge date)

| Metric | Before | After | Change |
|---|---|---|---|
| PR cycle time (median) | 43.9 hours | 19.7 hours | **−55%** |
| Change failure rate | ~35% of releases | ~5% of releases | **−30 points** |
| Throughput (issues resolved/month) | 23 | 35 | **+52%** |
| PR volume/week | 3–6 | 7–10 | **~1.7×** |

*(Reproduce: seed the demo data, then load `pull_requests`/`releases`/`issues`
for `acme/widgets` via `dora.storage.db`, run `dora.metrics.dora.summary(...)`
and `dora.metrics.flow.throughput(...)`, and compare the first and last
quartile of merged PRs by `merged_at`.)*

## How this maps to the resume claim

The resume claim — work completed 5→12 items/person/month, PRs merged
3→8/month, cycle time improved ~30% — is a real result from real team data,
not from this repo. What this simulation demonstrates is not "the same
numbers," it's **the same shape of result, produced by the same kind of
system**: a metrics pipeline that can detect and quantify exactly this
category of improvement, end to end, from raw event ingestion to a defensible
number. That's the point of the artifact — proof the measurement
infrastructure exists and works, independent of which specific team's data
runs through it.

## Caveats

- This is simulated data with a built-in trend, not a blind before/after —
  it's a demonstration of measurement capability, not a case study. It
  should never be presented as a real result; the framing above is "here is
  what my system detects," not "here is what I achieved with this repo."
- Change failure rate here uses the proxy defined in
  [metrics.md](metrics.md) (hotfix-keyword merges within 24h of a release);
  the "35%→5%" figure reflects the generator's `failure_chance` parameter,
  not an independent measurement.

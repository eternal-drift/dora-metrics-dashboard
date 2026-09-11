# VP Engineering Dashboard

The one page a VP of Engineering reads before a leadership review — five
numbers, their trend, and the one sentence of "why," not the full drill-down
a team lead needs. Everything here rolls up from
[engineering-health-scorecard.md](engineering-health-scorecard.md); this
page answers "so what," the scorecard answers "how do you know."

## Headline (sample, from seeded demo data)

> Engineering velocity and stability both improved this quarter. PR cycle
> time is down 55% (44h → 20h), change failure rate is down from ~35% to
> ~5%, and throughput is up 52% — **we are not trading speed for
> reliability, both moved in the same direction.** This is the signature
> pattern of process and scoping improvements (tighter PRs, faster review
> SLAs, better release hygiene), not of cutting corners.

## The five numbers a VP actually needs

| # | Metric | This period | Trend | So what |
|---|---|---|---|---|
| 1 | Deployment frequency | ~weekly | → stable | Ships are happening on a predictable cadence, not batched into risky big-bang releases |
| 2 | Change failure rate | ~5% | ↓ from ~35% | Releases are safer, not just faster — see headline framing above |
| 3 | PR cycle time | 19.7h median | ↓ from 43.9h | Work is moving through review faster; check [engineering-health-scorecard.md](engineering-health-scorecard.md) before crediting this to any single initiative |
| 4 | Throughput | 35 issues/mo | ↑ from 23 | Team capacity is growing faster than headcount — worth investigating whether this is sustainable or a short-term push |
| 5 | MTTR | no incident data this period | — | Absence of incidents is good news only if it reflects reality — flag if incident-tracking discipline has lapsed |

## Question this page is built to survive

*"Are you trading deployment frequency for reliability?"* — the honest
answer requires both numbers moving in the same visible direction, which is
exactly what row 1 and row 2 show together. If they ever diverge (frequency
up, failure rate also up), that's the one pattern this dashboard is
designed to make impossible to miss — it would show as a red change-failure-rate
cell next to a green deployment-frequency cell on the scorecard, not
smoothed into a single "health" number (see the scorecard's explicit
refusal to compute one).

## What this page intentionally omits

Per-engineer numbers, team-vs-team comparison, and anything that could be
read as an individual performance signal. This is a systems-health view,
not a review input — see [threat-model.md](threat-model.md) for why that
boundary is treated as a security/misuse concern, not just a style choice.

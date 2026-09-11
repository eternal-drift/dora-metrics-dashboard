# DORA Metrics Dashboard

Engineering flow metrics — deployment frequency, lead time for changes, PR cycle time,
and change failure rate — ingested from the GitHub API and visualized in Streamlit.

These are the four [DORA metrics](https://dora.dev/) plus PR cycle time, computed
directly from real GitHub data (pull requests, reviews, releases, deployments)
rather than self-reported numbers.

## How it works

1. **Ingest** (`cli.py`) pulls PRs, reviews, releases, and deployments for a repo
   from the GitHub REST API and stores them in SQLite (`dora/ingest`, `dora/storage`).
2. **Compute** (`dora/metrics/dora.py`) turns the raw data into the four metrics.
3. **Visualize** (`dashboard.py`) is a Streamlit app with headline tiles, charts,
   and a raw-data drill-down.

### Metric definitions

| Metric | Definition |
|---|---|
| PR cycle time | Hours from PR open to merge (also tracks time-to-first-review) |
| Deployment frequency | Count of releases (or deployments) per day/week/month |
| Lead time for changes | Hours from a PR's merge to the next release published afterward |
| Change failure rate | Fraction of releases followed within a configurable window by a PR merge whose title matches a hotfix/revert/rollback/incident keyword |

Lead time and change failure rate have no first-class "shipped to prod and broke"
signal in the plain GitHub REST API, so both use **documented proxies** (see comments
in `dora/metrics/dora.py`) rather than pretending to a ground-truth measurement. If a
repo doesn't cut releases, lead time will be empty — deployments can be substituted
via `--environment` on ingest.

### Flow & SPACE-inspired metrics

Beyond the four DORA metrics, `dora/metrics/flow.py` adds MTTR, WIP, throughput, and
SPACE-inspired indicators, computed from Jira-style issue events:

| Metric | Definition | Caveat |
|---|---|---|
| MTTR | Hours from an incident issue's creation to its resolution | No separate detection-time signal exists, so this overstates MTTR if incidents are filed after detection/triage has already begun |
| WIP | Count of issues started but not resolved, sampled at the end of each period | Point-in-time snapshot, not a period average — spikes between samples are invisible |
| Throughput | Count of issues resolved per period | Counts completed work items, distinct from deployment frequency (which counts ships) |
| SPACE (Activity, Performance, Efficiency) | PRs opened, issues resolved, and median PR cycle time per period, as proxies for the corresponding SPACE dimensions | Satisfaction and Communication have no signal in GitHub/Jira event data (no surveys, no comment/chat volume ingested) and are intentionally returned as `None` rather than approximated |

**There is no live Jira ingestion.** Issue events come from
`scripts/seed_demo_data.py`, which generates Jira-shaped synthetic issues
(stories, bugs, incidents) on the same timeline as the synthetic PRs/releases,
stored in the `issues` table (`dora/storage/db.py`).

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set a GitHub token (raises API rate limits from 60/hr to 5000/hr; also required for
private repos):

```bash
export GITHUB_TOKEN=ghp_...
```

## Usage

Ingest a repo:

```bash
python cli.py ingest owner/repo --limit 500
```

Or seed synthetic demo data with no token/API calls needed:

```bash
python scripts/seed_demo_data.py acme/widgets
```

Run the dashboard:

```bash
streamlit run dashboard.py
```

## Tests

```bash
pytest
```

## Configuration

Environment variables (see `dora/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | — | GitHub API auth |
| `DORA_DB_PATH` | `dora.db` | SQLite file location |
| `DORA_HOTFIX_WINDOW_HOURS` | `24` | Change-failure-rate window |

## Docs

This project's ambitions go beyond the current dashboard — see
[docs/roadmap.md](docs/roadmap.md) for where it's headed (an AI Engineering
Advisor, a Metrics API, real backing services). The rest of `docs/` covers
how the system is meant to be run and reasoned about as an engineering
intelligence platform, not just a script:

- [docs/metrics.md](docs/metrics.md) — full metric definitions and caveats
- [docs/adr/](docs/adr/) — architecture decision records
- [docs/vp-dashboard.md](docs/vp-dashboard.md) — the VP Engineering one-pager
- [docs/engineering-health-scorecard.md](docs/engineering-health-scorecard.md) — per-metric status rules and a sample scorecard
- [docs/quarterly-review.md](docs/quarterly-review.md) — a sample quarterly engineering review
- [docs/before-after-intervention.md](docs/before-after-intervention.md) — a simulated before/after improvement story from the seeded demo data
- [docs/cost-model.md](docs/cost-model.md) — infra cost at three scale points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-style threat model, including insider misuse of per-person metrics
- [docs/scalability-assumptions.md](docs/scalability-assumptions.md) — current scale assumptions and where they break

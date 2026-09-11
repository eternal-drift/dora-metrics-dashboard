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
| `ANTHROPIC_API_KEY` | — | Enables the AI Engineering Advisor (see below) |
| `ADVISOR_MODEL` | `claude-opus-5` | Model used by the Advisor |
| `DATABASE_URL` | — (falls back to SQLite at `DORA_DB_PATH`) | Set to a `postgresql://...` URL to use Postgres instead of SQLite |
| `QUEUE_URL` | — (falls back to an in-process queue) | Set to a `redis://...` URL to use Redis as the event queue |
| `GITHUB_WEBHOOK_SECRET` | — | If set, required to validate `POST /webhooks/github` deliveries |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — (falls back to console export) | Set to a `host:4317` OTLP endpoint (e.g. `tempo:4317`) to export traces there instead |
| `WORKER_METRICS_PORT` | `9100` | Port the worker exposes Prometheus metrics on |

## Metrics API

A read-only FastAPI surface over the same metrics the dashboard and Advisor use (`dora/api/main.py`):

```bash
uvicorn dora.api.main:app --reload
curl localhost:8000/repos/acme/widgets/health
```

## Webhook ingestion (event queue)

Polling (`cli.py ingest`) is still the right tool for a first backfill, but ongoing updates
can flow in via GitHub webhooks instead of re-polling: `POST /webhooks/github` (configure
this URL as a repo webhook, events: Pull requests, Pull request reviews, Releases,
Deployment statuses) verifies the signature, enqueues the event, and returns immediately.
A separate worker process applies queued events to storage:

```bash
python cli.py worker
```

See [docs/adr/0006-webhook-ingestion-and-event-queue.md](docs/adr/0006-webhook-ingestion-and-event-queue.md).

## Observability (OpenTelemetry + Prometheus + Grafana)

The API and worker are instrumented for the *platform's own* operational health — request
rate/latency, events processed/failed, processing time, queue depth — separate from the
engineering metrics the platform computes about other teams' repos. Traces propagate through
the event queue, so a webhook delivery and the worker turn that processes it show up as one
trace across two services. See [docs/adr/0007](docs/adr/0007-observability-otel-prometheus-grafana.md).

## Running everything with Docker Compose

Brings up Postgres, Redis, Tempo, Prometheus, Grafana, the Metrics API, the event-queue
worker, and the Streamlit dashboard as one stack:

```bash
docker compose up --build
# dashboard: http://localhost:8501, API: http://localhost:8000, webhooks: http://localhost:8000/webhooks/github
# Grafana: http://localhost:3000 (anonymous admin access, for local dev)
# Prometheus: http://localhost:9090, Tempo: http://localhost:3200
```

Seed or ingest against the same Postgres instance from the host (the compose file
publishes port 5432):

```bash
DATABASE_URL=postgresql://dora:dora@localhost:5432/dora python scripts/seed_demo_data.py acme/widgets
```

## AI Engineering Advisor

Ask natural-language questions about engineering health — "why did PR cycle time increase?",
"are we trading deployment frequency for reliability?", "summarize engineering health for the
VP" — and get answers grounded in the same metrics as the dashboard, via Claude tool calling
(`dora/advisor/`). Every answer carries the same caveats shown in [docs/metrics.md](docs/metrics.md);
the Advisor refuses to rank or evaluate individual engineers (see [docs/threat-model.md](docs/threat-model.md)).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python cli.py advise "which repo has the worst change failure rate?"
```

Or use the chat panel at the bottom of the Streamlit dashboard. See
[docs/roadmap.md](docs/roadmap.md) for what's intentionally out of scope for v0 (no
vector-DB RAG — caveats are embedded directly in the system prompt; no conversation
persistence).

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

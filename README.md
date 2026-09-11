# DORA Metrics Dashboard ("EngPulse")

An engineering-management intelligence platform: it ingests GitHub (and Jira-shaped synthetic)
engineering events and computes the four [DORA metrics](https://dora.dev/) plus PR cycle time,
flow metrics (WIP, throughput, MTTR), and SPACE-inspired indicators — then puts an AI Advisor
on top of them that can answer plain-language questions about engineering health, grounded in
that same data.

It started as a single-repo Streamlit dashboard and has grown into a small distributed system:
webhook-driven ingestion, an event queue, a worker, a read-only Metrics API, Postgres, and a
full observability stack (OpenTelemetry + Prometheus + Grafana) for the platform's own
operational health. Every piece is real and independently verified — see the docs under
[`docs/`](docs/) for the architecture decisions, caveats, and what's still intentionally
out of scope.

## Contents

- [Tech stack](#tech-stack)
- [User flows](#user-flows)
- [Architecture](#architecture)
- [Setup](#setup)
- [Usage](#usage)
- [Configuration](#configuration)
- [Tests](#tests)
- [Docs](#docs)

## Tech stack

| Layer | Technology | Where |
|---|---|---|
| Language / runtime | Python 3.12 | throughout |
| Dashboard UI | [Streamlit](https://streamlit.io/) + [Plotly](https://plotly.com/python/) | `dashboard.py` |
| CLI | [Typer](https://typer.tiangolo.com/) | `cli.py` |
| Metrics computation | [pandas](https://pandas.pydata.org/) | `dora/metrics/` |
| Metrics API | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) | `dora/api/` |
| AI Advisor | [Anthropic Claude API](https://docs.claude.com/) (tool calling, `claude-opus-5` by default) | `dora/advisor/` |
| Storage | [SQLite](https://sqlite.org/) (default) or [PostgreSQL](https://www.postgresql.org/) via [SQLAlchemy Core](https://www.sqlalchemy.org/) | `dora/storage/db.py` |
| Event queue | In-process (dev/test default) or [Redis](https://redis.io/) | `dora/queue/` |
| Webhook ingestion | GitHub webhooks, HMAC-verified | `dora/webhooks/`, `dora/api/webhooks.py` |
| Event processor | Standalone Python worker process | `dora/worker.py` |
| Tracing | [OpenTelemetry](https://opentelemetry.io/) → [Grafana Tempo](https://grafana.com/oss/tempo/) | `dora/observability/tracing.py` |
| Metrics (platform health) | [Prometheus](https://prometheus.io/) (`prometheus-fastapi-instrumentator` + `prometheus_client`) | `dora/observability/metrics.py` |
| Dashboards (platform health) | [Grafana](https://grafana.com/) (provisioned datasources + dashboard) | `observability/grafana/` |
| Containerization | [Docker](https://www.docker.com/) + [Docker Compose](https://docs.docker.com/compose/) | `Dockerfile`, `docker-compose.yml` |
| CI | [GitHub Actions](https://github.com/features/actions) (SQLite + Postgres + Redis test matrix) | `.github/workflows/ci.yml` |
| External API | GitHub REST API | `dora/ingest/github.py` |
| Testing | pytest, FastAPI `TestClient`, real Postgres/Redis containers in CI | `tests/` |

**Why each piece, not just what**: every non-obvious technology choice is written up as an ADR
in [`docs/adr/`](docs/adr/) — e.g. why SQLite-then-Postgres instead of Postgres-from-day-one, why
Redis instead of SQS/Kafka, why Tempo instead of Jaeger. Read those before assuming a choice was
arbitrary.

## User flows

### 1. Analyst/EM: explore metrics for a repo

```
seed or ingest data  →  streamlit run dashboard.py  →  select repo  →  read DORA/flow/SPACE
                                                                        tiles + charts
                                                     →  ask the AI Advisor a question
                                                        in the chat panel at the bottom
```

`python scripts/seed_demo_data.py acme/widgets` (synthetic, no token needed) or
`python cli.py ingest owner/repo` (real GitHub data) populates storage. The dashboard reads
straight from `dora.metrics`/`dora.advisor.context` — no separate build step.

### 2. Developer: query metrics programmatically

```
GET /repos                                    → which repos have data
GET /repos/{owner}/{name}/metrics/{metric}    → one metric's snapshot + trend + caveat
GET /repos/{owner}/{name}/health              → every metric at once (VP-summary shape)
```

`uvicorn dora.api.main:app` serves this. The Advisor's tools call the exact same
`dora.advisor.context` functions, so the API, the dashboard, and the Advisor never disagree
about a number.

### 3. Leader: ask the AI Advisor a question

```
"why did PR cycle time increase this sprint?"
"are we trading deployment frequency for reliability?"
"summarize engineering health for the VP"
        ↓
Claude (tool calling) → dora.advisor.tools → dora.advisor.context → dora.metrics → storage
        ↓
answer, with the metric's caveat attached (never a bare number)
```

Available via `python cli.py advise "<question>"` or the dashboard's chat panel. The system
prompt (`dora/advisor/prompts.py`) refuses to rank individual engineers — see
[`docs/threat-model.md`](docs/threat-model.md).

### 4. Ongoing ingestion: webhook → queue → worker (no re-polling)

```
GitHub event (PR merged, review submitted, release published, deploy status changed)
        ↓ HMAC-signed webhook POST
dora/api/webhooks.py  →  verify signature → normalize → enqueue  →  returns immediately
        ↓ (Redis, or in-process for dev/test)
dora/worker.py  →  consumes event → applies via dora.storage.db  →  same storage as polling
```

The webhook receiver never touches the database — it hands off to the queue and returns, so a
slow or failing write can't block accepting new deliveries. `python cli.py ingest` (polling)
remains the tool for a first backfill; webhooks only cover events going forward. See
[`docs/adr/0006`](docs/adr/0006-webhook-ingestion-and-event-queue.md).

### 5. Operator: run and observe the whole platform

```
docker compose up --build
        ↓
postgres, redis, tempo, prometheus, grafana, api, worker, dashboard — one stack
        ↓
Grafana (localhost:3000): API request rate/latency, worker throughput/latency by event
kind, queue depth, failure rate — plus full distributed traces in Tempo, spanning the
webhook receiver and the worker as one trace even though they're different containers
```

This is the platform's *own* operational health — separate from the engineering metrics it
computes about other teams. See [`docs/adr/0007`](docs/adr/0007-observability-otel-prometheus-grafana.md).

## Architecture

```
GitHub API (polling)  ──────────────────┐
                                         ▼
GitHub webhooks ──▶ dora/api/webhooks.py │
  (HMAC-verified)         │              │
                          ▼              │
                  dora/queue/            │
                (in-process or Redis)    │
                          │              │
                          ▼              ▼
                  dora/worker.py ──▶ dora/storage/db.py ──▶ SQLite or Postgres
                          │                                       │
                          │                                       ▼
                          │                          dora/metrics/ (DORA, flow, SPACE)
                          │                                       │
                          │                    ┌──────────────────┼───────────────────┐
                          │                    ▼                  ▼                    ▼
                          │            dashboard.py         dora/api/main.py    dora/advisor/
                          │            (Streamlit)           (FastAPI)      (Claude tool calling)
                          │
                          ▼
          dora/observability/ (OpenTelemetry + Prometheus)
                          │
                          ▼
              Tempo + Prometheus + Grafana
        (platform's own operational health, not the
         engineering metrics computed above)
```

Every metric that isn't a direct measurement (lead time, change failure rate, MTTR) is a
**documented proxy** — see [`docs/metrics.md`](docs/metrics.md) before presenting any number from
this system as ground truth.

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

### Ingest or seed data

```bash
python cli.py ingest owner/repo --limit 500      # real GitHub data
python scripts/seed_demo_data.py acme/widgets    # synthetic, no token/API calls needed
```

### Dashboard

```bash
streamlit run dashboard.py
```

### Metrics API

```bash
uvicorn dora.api.main:app --reload
curl localhost:8000/repos/acme/widgets/health
```

### AI Engineering Advisor

Ask natural-language questions about engineering health — "why did PR cycle time increase?",
"are we trading deployment frequency for reliability?", "summarize engineering health for the
VP" — grounded in the same metrics as the dashboard, via Claude tool calling. Every answer
carries the caveats from [`docs/metrics.md`](docs/metrics.md); the Advisor refuses to rank or
evaluate individual engineers (see [`docs/threat-model.md`](docs/threat-model.md)).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python cli.py advise "which repo has the worst change failure rate?"
```

Or use the chat panel at the bottom of the Streamlit dashboard. See
[`docs/roadmap.md`](docs/roadmap.md) for what's intentionally out of scope for v0 (no
vector-DB RAG — caveats are embedded directly in the system prompt; no conversation
persistence).

### Webhook ingestion (event queue)

Polling is still the right tool for a first backfill, but ongoing updates can flow in via
GitHub webhooks instead of re-polling: `POST /webhooks/github` (configure this URL as a repo
webhook, events: Pull requests, Pull request reviews, Releases, Deployment statuses) verifies
the signature, enqueues the event, and returns immediately. A separate worker process applies
queued events to storage:

```bash
python cli.py worker
```

See [`docs/adr/0006`](docs/adr/0006-webhook-ingestion-and-event-queue.md).

### Observability (OpenTelemetry + Prometheus + Grafana)

The API and worker are instrumented for the *platform's own* operational health — request
rate/latency, events processed/failed, processing time, queue depth — separate from the
engineering metrics the platform computes about other teams' repos. Traces propagate through
the event queue, so a webhook delivery and the worker turn that processes it show up as one
trace across two services. See [`docs/adr/0007`](docs/adr/0007-observability-otel-prometheus-grafana.md).

### Running everything with Docker Compose

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

## Configuration

Environment variables (see `dora/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | — | GitHub API auth |
| `DORA_DB_PATH` | `dora.db` | SQLite file location (used when `DATABASE_URL` is unset) |
| `DATABASE_URL` | — (falls back to SQLite) | Set to a `postgresql://...` URL to use Postgres instead |
| `DORA_HOTFIX_WINDOW_HOURS` | `24` | Change-failure-rate proxy window |
| `ANTHROPIC_API_KEY` | — | Enables the AI Engineering Advisor |
| `ADVISOR_MODEL` | `claude-opus-5` | Model used by the Advisor |
| `QUEUE_URL` | — (falls back to an in-process queue) | Set to a `redis://...` URL to use Redis as the event queue |
| `GITHUB_WEBHOOK_SECRET` | — | If set, required to validate `POST /webhooks/github` deliveries |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — (falls back to console export) | Set to a `host:4317` OTLP endpoint (e.g. `tempo:4317`) to export traces there instead |
| `OTEL_SERVICE_NAME_API` / `OTEL_SERVICE_NAME_WORKER` | `dora-api` / `dora-worker` | Service names traces are tagged with |
| `WORKER_METRICS_PORT` | `9100` | Port the worker exposes Prometheus metrics on |

## Tests

```bash
pytest
```

44 tests, covering: DORA/flow metric correctness (`tests/test_metrics.py`,
`tests/test_flow_metrics.py`), the Advisor's snapshot layer (`tests/test_advisor_context.py`),
the Metrics API (`tests/test_api.py`), the event queue (`tests/test_queue.py`), webhook signature
verification and payload normalization (`tests/test_webhooks.py`), and the full
webhook → queue → worker → storage flow (`tests/test_worker.py`). CI
(`.github/workflows/ci.yml`) runs the suite against SQLite, against a real Postgres service
container, and a separate webhook/Redis/Postgres smoke test — not just against whatever backend
happens to be configured locally.

## Docs

This project's ambitions go beyond the dashboard — see [`docs/roadmap.md`](docs/roadmap.md) for
what's built vs. still planned. The rest of `docs/` covers how the system is meant to be run and
reasoned about as an engineering intelligence platform, not just a script:

- [docs/metrics.md](docs/metrics.md) — full metric definitions and caveats
- [docs/adr/](docs/adr/) — architecture decision records (storage, proxy metrics, synthetic data, Streamlit-vs-React, the Advisor, webhooks/queue, observability)
- [docs/vp-dashboard.md](docs/vp-dashboard.md) — the VP Engineering one-pager
- [docs/engineering-health-scorecard.md](docs/engineering-health-scorecard.md) — per-metric status rules and a sample scorecard
- [docs/quarterly-review.md](docs/quarterly-review.md) — a sample quarterly engineering review
- [docs/before-after-intervention.md](docs/before-after-intervention.md) — a simulated before/after improvement story from the seeded demo data
- [docs/cost-model.md](docs/cost-model.md) — infra cost at three scale points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-style threat model, including insider misuse of per-person metrics
- [docs/scalability-assumptions.md](docs/scalability-assumptions.md) — current scale assumptions and where they break

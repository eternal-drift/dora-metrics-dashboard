# Roadmap

Where this project (currently: GitHub ingest → SQLite → DORA/flow/SPACE
metrics → Streamlit) is headed toward the full "EngPulse" engineering
intelligence platform. Ordered by dependency, not just priority — later
items build on earlier ones.

## Done

- GitHub ingestion (PRs, reviews, releases, deployments) → SQLite
- Synthetic Jira-shaped issue data for WIP/throughput/MTTR/SPACE (no live Jira ingest — see [ADR 0003](adr/0003-synthetic-jira-instead-of-live-integration.md))
- DORA metrics (deployment frequency, lead time, PR cycle time, change failure rate) with documented proxies — [metrics.md](metrics.md)
- Flow + SPACE-inspired metrics (MTTR, WIP, throughput, activity/performance/efficiency)
- Streamlit dashboard
- Strategy artifacts: ADRs, metric definitions, VP dashboard, engineering-health scorecard, sample quarterly review, cost model, threat model, scalability assumptions (this pass)

## Done: AI Engineering Advisor v0

- `dora/advisor/` — Claude tool-calling agent over `dora.metrics` (via a thin,
  unit-tested `context.py` snapshot layer), a Streamlit chat panel, and a
  `python cli.py advise "..."` command. See [ADR 0005](adr/0005-advisor-tool-calling-over-vector-rag.md)
  for why v0 skips vector-DB RAG in favor of tool calling + an embedded
  caveat corpus.
- Every tool result carries its own caveat field; the system prompt
  requires caveats to be stated whenever a metric is used, and refuses
  per-person ranking — implementing [threat-model.md](threat-model.md)'s
  top risk as a prompt-level guardrail, not an afterthought.
- Answers the five target questions directly (cycle-time regression,
  bottleneck identification, deploy-frequency-vs-reliability tradeoff,
  unhealthy WIP, VP-level summary) — see the system prompt's explicit
  per-question guidance in `dora/advisor/prompts.py`.
- **Not yet done**: FastAPI endpoint (currently in-process only, called
  directly from Streamlit/CLI), conversation persistence, vector-DB RAG for
  a larger knowledge corpus, streaming responses.

## Done: Postgres, Metrics API, Docker Compose, CI

- **Postgres** ([ADR 0001](adr/0001-storage-sqlite-then-postgres.md)) — `dora/storage/db.py` rewritten on SQLAlchemy Core; SQLite stays the default, set `DATABASE_URL` for Postgres. Verified against both a real `postgres:16-alpine` container and SQLite.
- **Metrics API** (`dora/api/main.py`, FastAPI) — read-only HTTP surface over the same `dora.advisor.context` snapshot layer the Advisor's tools use, so the dashboard, Advisor, and API compute metrics one way ([ADR 0004](adr/0004-streamlit-before-react.md) update). Streamlit itself still calls the snapshot layer in-process — no second *UI* consumer yet, so it doesn't call the API over HTTP.
- **Docker Compose** — `docker-compose.yml` brings up Postgres + the Metrics API + the Streamlit dashboard as one stack; built and run end-to-end (all three containers, real Postgres, seeded data, live API query) as part of shipping this.
- **GitHub Actions CI** — `.github/workflows/ci.yml` runs the full test suite against both SQLite and a real Postgres service container, plus a seed+API smoke test on the Postgres job.
- **Not yet done**: connection pooling tuning for concurrent load, migrations tooling (Alembic) — schema changes currently rely on `CREATE TABLE IF NOT EXISTS`, fine for additive changes, not for altering existing columns.

## Done: webhook ingestion + event queue

- **Webhook receiver** (`dora/api/webhooks.py`) — verifies GitHub's HMAC signature, normalizes `pull_request`/`pull_request_review`/`release`/`deployment_status` payloads, enqueues, returns without touching the DB.
- **Event queue** (`dora/queue/`) — `InMemoryQueue` (dev/test default) or `RedisQueue` (`QUEUE_URL=redis://...`), one interface. See [ADR 0006](adr/0006-webhook-ingestion-and-event-queue.md) for why Redis instead of SQS/Kafka for now.
- **Processor** (`dora/worker.py`, `python cli.py worker`) — separate process, same `db.upsert_*` write path as polling ingest.
- Verified as real decoupling, not just structure: run as independent Docker containers (`docker-compose.yml` adds `redis` and `worker` services) communicating only through Redis, including surviving an independent worker rebuild/restart mid-flow.
- Polling (`cli.py ingest`) is kept for first-time backfill; webhooks only cover events going forward.
- **Not yet done**: SQS/Kafka (deferred per ADR 0006 until real durability/ordering guarantees are needed), an outbox pattern or retry queue for the known `pull_request_review`-before-`pull_request` ordering gap, dead-letter handling for poison messages ([scalability-assumptions.md](scalability-assumptions.md)).

## Done: OpenTelemetry + Prometheus + Grafana

- **Metrics** — `prometheus-fastapi-instrumentator` on the API, hand-written `prometheus_client` metrics in the worker (`dora/observability/metrics.py`): events processed/failed by kind, processing-time histogram, queue depth.
- **Tracing** — OpenTelemetry (`dora/observability/tracing.py`) with explicit context propagation across the event queue, so a webhook request and the worker turn that processes it join one trace across two containers. See [ADR 0007](adr/0007-observability-otel-prometheus-grafana.md).
- **Backend** — Grafana Tempo (traces) + Prometheus (metrics) + Grafana (provisioned datasources + a starter dashboard: API rate/latency, worker throughput/latency by kind, queue depth, failure rate) — `observability/` + `docker-compose.yml`.
- Verified as real, not just wired: full 7-service stack brought up together, a live webhook driven through it, and the resulting trace confirmed in Tempo to span both `dora-api` and `dora-worker` under one `trace_id`.
- **Not yet done**: alerting rules, SLO dashboards, trace sampling config (currently samples everything), log correlation with `trace_id`.

## Then: production-shaped infra

- ClickHouse for metric rollups at higher data volume ([scalability-assumptions.md](scalability-assumptions.md)).
- Terraform for the above, once the architecture is stable enough that infra-as-code isn't chasing a moving target.

## Later / optional

- React dashboard replacing Streamlit, once a second UI consumer or a
  stronger UX need justifies the investment ([ADR 0004](adr/0004-streamlit-before-react.md)).
- Live Jira ingestion, replacing synthetic issue data ([ADR 0003](adr/0003-synthetic-jira-instead-of-live-integration.md)).
- Multi-org / multi-tenant support, if this ever needs to serve more than one company's data — currently out of scope.

## Explicitly not planned

See [scalability-assumptions.md](scalability-assumptions.md)'s non-goals
section — sub-minute metric freshness and multi-region active-active are
deliberate scope exclusions, not deferred work.

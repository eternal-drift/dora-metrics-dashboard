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

## Then: real backing services

- **Postgres migration** ([ADR 0001](adr/0001-storage-sqlite-then-postgres.md)) — triggered by the Advisor needing concurrent read access alongside interactive ingestion/dashboard use.
- **Metrics API (FastAPI)** in front of `dora/metrics` — triggered by the Advisor becoming a second consumer of metrics alongside the dashboard ([ADR 0004](adr/0004-streamlit-before-react.md)).
- **Docker Compose** (app + Postgres, one-command local stack) and **GitHub Actions CI** (tests + lint on every PR) — cheap to add once the API exists, and the first real infra-credibility signal.

## Then: production-shaped infra

- Event queue (SQS/Kafka) decoupling ingestion from metric processing — see [scalability-assumptions.md](scalability-assumptions.md) for the trigger conditions.
- Webhook-driven ingestion replacing polling.
- OpenTelemetry instrumentation + Prometheus/Grafana for the platform's own operational health (not to be confused with the engineering metrics the platform computes about other teams).
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

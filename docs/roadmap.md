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

## Next: AI Engineering Advisor (highest narrative value, builds on existing metrics)

- FastAPI endpoint (or an in-Streamlit chat panel first, as a fast v0) that
  takes a natural-language question and answers it using `dora.metrics` as
  tool-calling functions (not by hand-writing SQL per question).
- RAG context: the metric caveats in [metrics.md](metrics.md) must be
  retrievable by the Advisor so answers carry the right caveats
  automatically — the Advisor should never state a proxy metric as fact
  without the caveat attached (see [ADR 0002](adr/0002-proxy-metrics-over-missing-signals.md)).
- Target the sample questions directly: cycle-time regression cause,
  bottleneck-service identification, deploy-frequency-vs-reliability
  tradeoff check, unhealthy-WIP detection, VP-level health summary.
- Guardrails from day one, not retrofitted: no per-person ranking without
  the caveat framing described in [threat-model.md](threat-model.md).

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

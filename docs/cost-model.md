# Cost Model

Rough monthly infra cost at three scale points, for the target architecture
(see [roadmap.md](roadmap.md)) — not the current SQLite/Streamlit state,
which costs whatever a laptop or a single small VM costs. Numbers are
order-of-magnitude estimates for planning conversations, not vendor quotes.

## Assumptions

- Managed cloud services (e.g. AWS/GCP-equivalent), not self-hosted k8s,
  to keep the estimate comparable across scale points.
- LLM cost is the Advisor's usage only — metric computation itself is cheap
  compute, not LLM calls, per [ADR — LLM used only for the Advisor layer].
- "Repo" below means one ingested GitHub repository; "team" means the
  people whose issues/PRs live in that repo.

## Scale point A — pilot (1–5 teams, ~10 repos)

| Component | Est. monthly cost | Notes |
|---|---|---|
| Postgres (small managed instance) | $25–50 | Single instance, no read replica needed yet |
| Ingestion + Metrics API compute | $20–40 | Low-traffic FastAPI service, small container |
| Event queue (SQS-equivalent) | ~$5 | Pilot volume is well within free/near-free tier |
| LLM Advisor (RAG + tool calling) | $30–100 | Depends on query volume; a VP asking 5 questions/week costs far less than a self-serve tool used by every EM daily |
| Observability (Prometheus/Grafana-equivalent) | $0–20 | Can run on the same small instance at this scale |
| **Total** | **~$100–250/mo** | |

## Scale point B — org-wide (20–50 teams, ~200 repos)

| Component | Est. monthly cost | Notes |
|---|---|---|
| Postgres (or ClickHouse for metric aggregates) | $200–500 | Read replica likely needed; ClickHouse if query patterns are heavy on time-series rollups |
| Ingestion + Metrics API compute | $150–400 | Multiple ingestion workers, autoscaled API |
| Event queue/stream | $50–150 | Kafka-equivalent managed service, or SQS at higher volume |
| LLM Advisor | $300–1000 | Self-serve usage across teams; cacheable prompts (see [claude-api skill guidance] on caching) meaningfully reduce this |
| Observability | $50–150 | Dedicated instance, longer retention |
| **Total** | **~$750–2200/mo** | Roughly $15–45/team/month |

## Scale point C — enterprise (100+ teams, 1000+ repos)

| Component | Est. monthly cost | Notes |
|---|---|---|
| ClickHouse cluster | $1500–4000 | Metric aggregation at this volume favors columnar storage over row-oriented Postgres |
| Ingestion + Metrics API compute | $800–2000 | Horizontally scaled, likely multi-region if the org is |
| Event stream (Kafka) | $500–1500 | Dedicated cluster, not shared/managed-lite tier |
| LLM Advisor | $1500–5000 | High query volume; prompt caching and a smaller model for routine questions become load-bearing cost controls, not just optimizations |
| Observability | $300–800 | Full Prometheus/Grafana stack, long retention, alerting |
| **Total** | **~$4600–13,300/mo** | Roughly $45–130/team/month — cost per team should trend down with scale if the architecture is right; if it isn't, that's a signal to revisit ClickHouse/queue sizing |

## Cost control levers (in priority order)

1. **LLM prompt caching** for the Advisor — repeated system-prompt/RAG-context tokens are the highest-leverage lever at scale B and beyond.
2. **Metric pre-aggregation** (materialized rollups per period) instead of recomputing from raw events on every dashboard/Advisor query — keeps Postgres/ClickHouse load flat as history grows.
3. **Tiered LLM routing** — a smaller/cheaper model for routine "what's my cycle time" queries, reserving a larger model for open-ended "why did X happen" reasoning.
4. **Ingestion polling interval** — GitHub webhook-driven ingestion (event-triggered) is both cheaper and fresher than polling, and should replace polling once webhook infra exists.

# Scalability Assumptions

What this system assumes about scale today, where those assumptions break,
and what changes when they do. Paired with [cost-model.md](cost-model.md)
(cost at each scale point) and [roadmap.md](roadmap.md) (when each change
lands).

## Current state (SQLite + Streamlit + synchronous ingestion)

**Assumptions baked in:**
- Single writer at a time (SQLite's write lock) — fine for one interactive
  user running ingestion and viewing the dashboard sequentially.
- Ingestion is synchronous and pull-based (`cli.py ingest` blocks until
  done) — fine for a handful of repos ingested on demand.
- All metric computation happens in-process on the full DataFrame for a
  repo (`dora/metrics/*.py` takes a full pandas DataFrame, not a windowed
  query) — fine while a repo's full PR/issue history fits comfortably in
  memory.
- The dashboard recomputes metrics on every load (`st.cache_data(ttl=60)`)
  rather than reading precomputed rollups — fine at low query volume.

**Where this breaks:** more than one person using the system
simultaneously against the same DB, more than a few dozen repos, or PR/issue
history in the hundreds of thousands of rows per repo (large monorepos with
years of history).

## Target architecture scale assumptions

| Layer | Assumption | Breaks at | Mitigation |
|---|---|---|---|
| Ingestion | Polling GitHub/Jira APIs per repo on a schedule | ~hundreds of repos on a shared polling budget hits API rate limits | Move to webhook-driven, event-triggered ingestion (push, not pull) — see [roadmap.md](roadmap.md) |
| Queue | Single queue, no partitioning | High event volume across many orgs causes head-of-line blocking for unrelated teams | Partition by org/repo so one noisy repo can't delay another's metrics |
| Metrics processors | Recompute full aggregates on each event | Recompute cost grows with history length, not just event rate | Incremental/streaming aggregation (append to rollups, don't replay full history) once event volume justifies it |
| Storage | Postgres row store | Metric-query patterns are heavily time-series/aggregate (sum/avg over date ranges) — row stores degrade on this pattern as row count grows | ClickHouse (or equivalent columnar store) for computed-metric rollups; Postgres stays authoritative for raw events/entities |
| Metrics API | Synchronous query-per-request | High concurrent dashboard/Advisor query volume against cold aggregates | Precomputed rollups (materialized per period) instead of query-time aggregation; cache layer in front of hot queries |
| LLM Advisor | One tool call per question, synchronous | Multi-step "why did X happen" investigations need several tool calls; latency compounds | Async tool-calling with streaming partial results; cap investigation depth with a budget, not an unbounded loop |

## Explicit non-goals at any scale point in this system's roadmap

- **Real-time (sub-minute) metric freshness.** Engineering metrics are
  meaningfully interpreted over days/weeks, not seconds — optimizing
  ingestion latency below "within the hour" trades engineering effort for
  a property nobody needs. This is a deliberate scope boundary, not a
  current limitation to fix later.
- **Multi-region active-active.** Engineering metrics platforms are
  internal tools with generous latency tolerance; single-region with
  standard DR (backups + a documented restore process) is sufficient
  through enterprise scale. Multi-region would be solving a problem this
  system doesn't have.

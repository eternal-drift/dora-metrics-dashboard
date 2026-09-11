# ADR 0007: OpenTelemetry + Prometheus + Grafana for the platform's own operational health

## Status
Accepted

## Context
[Roadmap](../roadmap.md) calls for "OpenTelemetry instrumentation + Prometheus/Grafana for the
platform's own operational health (not to be confused with the engineering metrics the platform
computes about other teams)." That distinction matters: this is about whether the *DORA platform
itself* (its API, its worker) is fast, correct, and not silently dropping events — a different
question from "is the team whose repo we're measuring shipping well."

The event queue (see [ADR 0006](0006-webhook-ingestion-and-event-queue.md)) makes this
concretely necessary, not just nice-to-have: a webhook delivery and the worker turn that
processes it happen in different processes, often different containers, connected only by
Redis. Without tracing, a slow or failed event is invisible — there's no single log to grep.

## Decision
- **Metrics**: `prometheus-fastapi-instrumentator` on the API (`GET /metrics`, free HTTP
  request-rate/latency/size metrics) and hand-written `prometheus_client` metrics in the worker
  (`dora/observability/metrics.py`: events processed/failed by kind, processing-time histogram,
  queue depth) exposed on its own port. Both are real Prometheus scrape targets, not
  self-reported logs.
- **Tracing**: OpenTelemetry (`dora/observability/tracing.py`), with explicit context
  propagation across the queue boundary — `inject_trace_context` in the webhook handler before
  enqueueing, `extract_trace_context` in the worker before starting its processing span. Without
  this, the API's request span and the worker's processing span would be two unrelated traces
  instead of one. **Verified, not just written**: a webhook POST and the worker span that
  processed it were confirmed in Tempo to share one `trace_id` across two different services
  running in two different containers.
- Console export by default (`ConsoleSpanExporter` via a `SimpleSpanProcessor`, not
  `BatchSpanProcessor` — avoids a background thread outliving the process, which caused noisy
  "I/O operation on closed file" errors under pytest); OTLP export to Tempo when
  `OTEL_EXPORTER_OTLP_ENDPOINT` is set, as it is in `docker-compose.yml`.
- **Backend**: Grafana Tempo for traces (OTLP-native, single lightweight container, no
  Jaeger/Collector needed), Prometheus for metrics, Grafana on top of both with provisioned
  datasources and one starter dashboard (`observability/grafana/`) — API request rate/latency,
  worker throughput/latency by event kind, queue depth, worker failure rate.

## Consequences
- The full stack (`postgres`, `redis`, `tempo`, `prometheus`, `grafana`, `api`, `worker`) was
  brought up together via Docker Compose and driven end-to-end: seeded data, sent a real webhook,
  confirmed Prometheus scraped both `dora-api` and `dora-worker` as `up`, confirmed the metric
  values reflected the real event, and confirmed Tempo held one trace spanning both services.
  This is the strongest evidence in this repo that the "decoupled ingestion" architecture
  ([ADR 0006](0006-webhook-ingestion-and-event-queue.md)) actually behaves like independent
  services rather than a single process pretending to be several.
- Metrics/tracing code lives in `dora/observability/`, imported by `dora/api/main.py` and
  `dora/worker.py` — not scattered inline, so it can be extended (e.g. more span attributes, a
  `dora.ingest` polling-path span) without touching business logic.
- Not done: alerting rules (Prometheus Alertmanager), SLO dashboards, trace sampling
  configuration (currently samples everything, fine at demo volume, wrong at production volume),
  log correlation (structured logs carrying `trace_id`). These are straightforward additions on
  top of what exists, not architectural changes — left for when there's a real on-call story to
  build them against.

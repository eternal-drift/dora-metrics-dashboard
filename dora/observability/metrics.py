"""Prometheus metrics for the worker process. The API's HTTP metrics come
for free from prometheus-fastapi-instrumentator (wired in dora/api/main.py);
these are metrics specific to queue consumption that an HTTP instrumentor
has no visibility into.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

EVENTS_PROCESSED = Counter(
    "dora_worker_events_processed_total",
    "Events successfully applied to storage, by event kind.",
    ["kind"],
)

EVENT_PROCESSING_SECONDS = Histogram(
    "dora_worker_event_processing_seconds",
    "Time to apply one event to storage, by event kind.",
    ["kind"],
)

EVENTS_FAILED = Counter(
    "dora_worker_events_failed_total",
    "Events that raised while being processed, by event kind.",
    ["kind"],
)

QUEUE_DEPTH = Gauge(
    "dora_worker_queue_depth",
    "Number of events currently waiting in the queue (best-effort; not all backends support len()).",
)

_metrics_server_started = False


def start_metrics_server(port: int) -> None:
    """Idempotent within a process -- safe to call on every run_worker()
    invocation (matters for tests, which call run_worker repeatedly in one
    pytest process)."""
    global _metrics_server_started
    if _metrics_server_started:
        return
    try:
        start_http_server(port)
        _metrics_server_started = True
    except OSError:
        # Port already bound -- most likely a previous call in this same
        # process raced past the flag check, or something else on the host
        # owns the port. Either way, don't crash the worker over metrics.
        _metrics_server_started = True

"""OpenTelemetry tracing setup, plus trace-context propagation across the
event queue -- the queue is a real process boundary (dora/api/webhooks.py
enqueues, dora/worker.py consumes, often in a different container), so
without explicit propagation a webhook delivery and the worker turn that
handles it would show up as two disconnected traces instead of one.
"""
from __future__ import annotations

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

from dora.config import settings

_initialized_services: set[str] = set()


def setup_tracing(service_name: str) -> trace.Tracer:
    """Idempotent per service_name (safe to call on every import/entrypoint).

    Exports to OTLP if OTEL_EXPORTER_OTLP_ENDPOINT is set (e.g. an OTel
    Collector or Tempo, as in docker-compose.yml); otherwise exports to the
    console, so tracing is visible (as log lines) with zero extra infra --
    see docs/adr/0007 for why that's the default rather than requiring a
    collector to run anything locally.
    """
    if service_name not in _initialized_services:
        provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
            # Async network export benefits from batching.
            provider.add_span_processor(BatchSpanProcessor(exporter))
        else:
            # Synchronous: no background thread to outlive the process (avoids
            # noisy "I/O operation on closed file" export errors on shutdown,
            # e.g. under pytest) -- fine since console export is the
            # zero-infra dev/test default, not a high-throughput path.
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _initialized_services.add(service_name)
    return trace.get_tracer(service_name)


def inject_trace_context(event: dict) -> dict:
    """Attach the current trace context to an outgoing queue event (call
    this where the event is enqueued, inside the span for that request)."""
    carrier: dict = {}
    inject(carrier)
    event["_trace_context"] = carrier
    return event


def extract_trace_context(event: dict) -> otel_context.Context:
    """Recover the trace context from a queue event (call this in the
    worker before starting the span that processes it)."""
    return extract(event.get("_trace_context") or {})

"""Operational observability for this platform's own services (the API and
the worker) -- OpenTelemetry tracing + Prometheus metrics. Not to be
confused with the engineering metrics (DORA, flow, SPACE) this platform
computes about other teams' repos; see docs/adr/0007.

Two pieces:
- tracing.py: OpenTelemetry spans, including propagating trace context
  through the event queue so a webhook delivery and the worker turn that
  processes it show up as one trace, not two unrelated ones.
- metrics.py: Prometheus counters/histograms/gauges for the worker (the API
  gets its HTTP metrics for free from prometheus-fastapi-instrumentator).
"""

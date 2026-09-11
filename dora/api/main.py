"""Metrics API.

Read-only HTTP surface over dora.advisor.context (the same snapshot layer
the AI Advisor's tools use), so the dashboard, the Advisor, and any future
consumer (a React frontend -- see docs/adr/0004) all see identical numbers
computed one way, instead of each reimplementing metric queries.

Run: uvicorn dora.api.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator

from dora.advisor import context
from dora.api.webhooks import router as webhooks_router
from dora.config import settings
from dora.observability.tracing import setup_tracing

app = FastAPI(
    title="DORA Metrics API",
    description="Read-only engineering metrics: DORA, PR cycle time, WIP, throughput, MTTR, SPACE-inspired indicators.",
    version="0.1.0",
)
app.include_router(webhooks_router)

setup_tracing(settings.otel_service_name_api)
FastAPIInstrumentor.instrument_app(app)
Instrumentator().instrument(app).expose(app)  # GET /metrics -- Prometheus scrape target


def _require_repo(repo: str) -> None:
    if repo not in context.repos():
        raise HTTPException(status_code=404, detail=f"No data ingested for repo '{repo}'.")


@app.get("/repos")
def list_repos() -> dict:
    return {"repos": context.repos()}


@app.get("/repos/{owner}/{name}/metrics/pr-cycle-time")
def pr_cycle_time(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.pr_cycle_time_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/change-failure-rate")
def change_failure_rate(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.change_failure_rate_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/deployment-frequency")
def deployment_frequency(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.deployment_frequency_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/lead-time")
def lead_time(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.lead_time_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/mttr")
def mttr(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.mttr_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/wip")
def wip(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.wip_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/throughput")
def throughput(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.throughput_snapshot(repo)


@app.get("/repos/{owner}/{name}/metrics/space")
def space_indicators(owner: str, name: str) -> dict:
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.space_snapshot(repo)


@app.get("/repos/{owner}/{name}/health")
def health_snapshot(owner: str, name: str) -> dict:
    """Every metric at once -- backs the VP dashboard / engineering-health scorecard views."""
    repo = f"{owner}/{name}"
    _require_repo(repo)
    return context.full_health_snapshot(repo)

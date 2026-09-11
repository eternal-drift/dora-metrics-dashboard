"""GitHub webhook receiver: verify signature, normalize, enqueue, return
fast. No DB write happens on this request path -- see dora/worker.py for
the consumer that actually applies events, and docs/adr/0006 for why the
two are split.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request

from dora.config import settings
from dora.observability.tracing import inject_trace_context
from dora.queue import get_queue
from dora.webhooks import normalize_event, verify_signature

router = APIRouter()


@router.post("/webhooks/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict:
    body = await request.body()

    if settings.github_webhook_secret:
        if not verify_signature(body, x_hub_signature_256, settings.github_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    event = normalize_event(x_github_event, payload)
    if event is None:
        return {"status": "ignored", "event_type": x_github_event}

    # FastAPIInstrumentor already opened a span for this request; propagate
    # it through the queue so the worker's processing span (a different
    # process, often a different container) joins the same trace.
    inject_trace_context(event)
    get_queue().enqueue(event)
    return {"status": "queued", "event_type": x_github_event, "repo": event["repo"]}

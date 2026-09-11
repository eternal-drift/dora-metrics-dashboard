"""GitHub webhook ingestion: verify -> normalize -> enqueue.

Replaces polling for repos that can register a webhook -- see
docs/adr/0006-webhook-ingestion-and-event-queue.md. `cli.py ingest` (polling)
still exists and is the right choice for a one-off backfill or a repo that
can't receive webhooks; this is the event-triggered path for repos that can.
"""
from __future__ import annotations

import hashlib
import hmac


def verify_signature(body: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify GitHub's X-Hub-Signature-256 header (sha256=<hex hmac>) against
    the raw request body, using constant-time comparison. See
    docs/threat-model.md's "forged webhook payload" ingestion risk."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)


def normalize_event(event_type: str, payload: dict) -> dict | None:
    """Map a raw GitHub webhook payload to the internal queue event shape
    {"repo": ..., "kind": ..., "data": ...} that dora.worker knows how to
    apply. Returns None for event types/actions we don't act on (still a
    valid webhook delivery -- just nothing to do)."""
    repo = payload.get("repository", {}).get("full_name")
    if not repo:
        return None

    if event_type == "pull_request":
        return {"repo": repo, "kind": "pull_request", "data": payload["pull_request"]}

    if event_type == "pull_request_review" and payload.get("action") == "submitted":
        review = payload["review"]
        return {
            "repo": repo,
            "kind": "pull_request_review",
            "data": {"number": payload["pull_request"]["number"], "submitted_at": review.get("submitted_at")},
        }

    if event_type == "release" and payload.get("action") == "published":
        return {"repo": repo, "kind": "release", "data": payload["release"]}

    if event_type == "deployment_status":
        return {"repo": repo, "kind": "deployment", "data": payload["deployment"]}

    return None

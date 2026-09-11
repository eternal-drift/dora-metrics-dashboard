"""Metrics processor: consumes normalized events off the queue and writes
them to storage. This is the "processors" box in the roadmap's
ingestion -> queue -> processors -> storage pipeline -- deliberately a
separate process/entrypoint from the webhook receiver (dora/api), so a slow
or failing write never blocks accepting new webhook deliveries.

Run: python -m dora.worker
"""
from __future__ import annotations

import time

from dora.queue import get_queue
from dora.storage import db


def process_event(conn, event: dict) -> None:
    repo = event["repo"]
    kind = event["kind"]
    data = event["data"]

    if kind == "pull_request":
        db.upsert_pull_requests(conn, repo, [data])
    elif kind == "release":
        db.upsert_releases(conn, repo, [data])
    elif kind == "deployment":
        db.upsert_deployments(conn, repo, [data])
    elif kind == "pull_request_review":
        # No-op if the pull_request event for this PR hasn't landed yet --
        # a known ordering gap with at-least-once, non-transactional
        # delivery across two event kinds. See docs/adr/0006.
        db.record_first_review(conn, repo, data["number"], data["submitted_at"])
    else:
        raise ValueError(f"Unknown event kind: {kind!r}")


def run_worker(max_events: int | None = None, poll_interval_seconds: int = 5) -> int:
    """Consume events until max_events have been processed (for tests/one-shot
    runs), or forever if max_events is None."""
    queue = get_queue()
    processed = 0
    while max_events is None or processed < max_events:
        got_any = False
        with db.connect() as conn:
            for event in queue.consume(block_seconds=poll_interval_seconds):
                got_any = True
                process_event(conn, event)
                processed += 1
                if max_events is not None and processed >= max_events:
                    break
        if max_events is not None:
            break
        if not got_any:
            time.sleep(poll_interval_seconds)
    return processed


if __name__ == "__main__":
    run_worker()

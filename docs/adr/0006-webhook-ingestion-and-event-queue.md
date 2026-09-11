# ADR 0006: Webhook ingestion via Redis-backed queue, not SQS/Kafka

## Status
Accepted

## Context
Polling (`cli.py ingest`) works for a one-off backfill but doesn't scale to
many repos and isn't fresh — see
[scalability-assumptions.md](../scalability-assumptions.md), which names
webhook-driven ingestion as the fix once polling's API-rate-limit budget
becomes the bottleneck. The target architecture sketch in
[roadmap.md](../roadmap.md) names SQS/Kafka as the queue between ingestion
and metric processing.

Standing up a real SQS queue or a Kafka cluster for a portfolio-scale
project is disproportionate to what it demonstrates: the architectural
property that matters here is **decoupling** — a webhook receiver that
returns fast and never blocks on a slow/failing metrics-store write — not
which specific broker provides it.

## Decision
- **Webhook receiver**: `dora/api/webhooks.py`, a FastAPI route
  (`POST /webhooks/github`) that verifies GitHub's HMAC signature
  (`dora/webhooks/verify_signature`, guarding against the forged-payload
  risk named in [threat-model.md](../threat-model.md)), normalizes the
  payload to `{repo, kind, data}` (`dora/webhooks/normalize_event`), enqueues
  it, and returns — no DB write on this request path.
- **Queue**: `dora/queue/`, one interface with two backends: `InMemoryQueue`
  (single-process, non-durable — dev/test default, no infra required) and
  `RedisQueue` (a Redis list via `RPUSH`/`BLPOP`) selected by setting
  `QUEUE_URL`. Redis is a genuine second process — the webhook receiver and
  the worker are provably decoupled, not just structured as if they were —
  while staying a `docker-compose` one-liner to run, unlike Kafka/SQS.
- **Processor**: `dora/worker.py` (`python -m dora.worker` /
  `python cli.py worker`), a separate process that consumes events and
  applies them via the same `dora.storage.db.upsert_*` functions the
  polling ingest path uses — one write path regardless of how data arrived.
- Polling (`cli.py ingest`) is kept, not replaced — it's still the right
  tool for a first backfill of a repo's history, which webhooks don't
  provide (they only fire on new events going forward).

## Consequences
- Real, verified decoupling: the receiver and processor were run as
  separate Docker containers, communicating only through Redis, and shown
  to survive the worker container being independently rebuilt/restarted.
- A genuine correctness gap, documented rather than hidden: `worker.py`'s
  handling of `pull_request_review` events is a no-op if the corresponding
  `pull_request` event hasn't been processed yet (out-of-order,
  at-least-once delivery across two event kinds, no transactional
  ordering). A production system would need either an outbox pattern or a
  deferred-retry queue for this; v0 accepts the gap and states it in
  `dora/worker.py`'s docstring rather than silently dropping the review.
- `InMemoryQueue` is explicitly not durable and not shared across
  processes — fine for tests and for running the API standalone without
  Redis, wrong for anything resembling production. `QUEUE_URL` is the
  documented switch.
- Moving to SQS/Kafka later is a new `Queue` implementation behind the same
  interface, not a rewrite of the webhook handler or the worker — see
  [roadmap.md](../roadmap.md).

"""Event queue decoupling webhook ingestion from metric-store writes.

Two backends behind one interface:

- InMemoryQueue: single-process, non-durable. Good for tests and for running
  the API without standing up Redis; events are lost if the process dies
  with events unconsumed. This is a stand-in, not a real queue -- see
  docs/adr/0006-webhook-ingestion-and-event-queue.md for why a full
  broker (SQS/Kafka) is deferred past this.
- RedisQueue: a Redis list used as a FIFO queue via RPUSH/BLPOP. Realistic
  enough to demo real decoupling (the webhook handler and the worker are
  genuinely separate processes) and trivial to run locally via
  docker-compose, without the operational weight of Kafka/SQS for a
  portfolio-scale project.

Select via QUEUE_URL (a redis:// URL); unset uses the in-memory backend.
"""
from __future__ import annotations

import collections
import json
from typing import Iterator, Protocol

from dora.config import settings


class Queue(Protocol):
    def enqueue(self, event: dict) -> None: ...
    def consume(self, block_seconds: int = 5) -> Iterator[dict]: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._q: collections.deque[dict] = collections.deque()

    def enqueue(self, event: dict) -> None:
        self._q.append(event)

    def consume(self, block_seconds: int = 5) -> Iterator[dict]:
        # Non-blocking: drains what's there now. A real queue would block
        # up to block_seconds waiting for new items (see RedisQueue).
        while self._q:
            yield self._q.popleft()

    def __len__(self) -> int:
        return len(self._q)


class RedisQueue:
    def __init__(self, url: str, list_key: str = "dora:events") -> None:
        import redis

        self._r = redis.from_url(url)
        self._key = list_key

    def enqueue(self, event: dict) -> None:
        self._r.rpush(self._key, json.dumps(event))

    def consume(self, block_seconds: int = 5) -> Iterator[dict]:
        import redis

        while True:
            try:
                item = self._r.blpop(self._key, timeout=block_seconds)
            except redis.exceptions.TimeoutError:
                # A BLPOP timeout can surface as a client-side socket timeout
                # rather than a clean None, depending on redis-py version and
                # network latency (observed over a Docker bridge network).
                # Same meaning either way: nothing arrived in time.
                return
            if item is None:
                return  # nothing arrived within the timeout; caller decides whether to re-poll
            _, raw = item
            yield json.loads(raw)

    def __len__(self) -> int:
        return self._r.llen(self._key)


_queue: Queue | None = None


def get_queue() -> Queue:
    """Process-wide queue instance, lazily selected from settings.queue_url.

    Deliberately a singleton so the in-memory backend actually behaves like
    a queue within one process (a fresh InMemoryQueue per call would just
    discard every event). Call reset_queue() in tests that need isolation.
    """
    global _queue
    if _queue is None:
        _queue = RedisQueue(settings.queue_url) if settings.queue_url else InMemoryQueue()
    return _queue


def reset_queue() -> None:
    global _queue
    _queue = None

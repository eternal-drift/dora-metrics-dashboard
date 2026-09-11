from dora.queue import InMemoryQueue


def test_enqueue_then_consume_preserves_order():
    q = InMemoryQueue()
    q.enqueue({"n": 1})
    q.enqueue({"n": 2})
    q.enqueue({"n": 3})
    assert [e["n"] for e in q.consume()] == [1, 2, 3]


def test_consume_drains_the_queue():
    q = InMemoryQueue()
    q.enqueue({"n": 1})
    list(q.consume())
    assert len(q) == 0
    assert list(q.consume()) == []


def test_empty_queue_consume_yields_nothing():
    q = InMemoryQueue()
    assert list(q.consume()) == []

"""Tests for event_bus.py — pub/sub determinism."""
import threading
import time

from orchestration.event_bus import EventBus, event_bus


class TestEventBus:
    def test_subscribe_and_emit(self):
        eb = EventBus()
        received = []

        eb.subscribe("test", lambda **kw: received.append(kw))
        eb.emit("test", key="value", num=42)

        assert len(received) == 1
        assert received[0]["key"] == "value"
        assert received[0]["num"] == 42

    def test_multiple_subscribers(self):
        eb = EventBus()
        r1, r2 = [], []

        eb.subscribe("test", lambda **kw: r1.append(kw))
        eb.subscribe("test", lambda **kw: r2.append(kw))
        eb.emit("test", x=1)

        assert len(r1) == 1
        assert len(r2) == 1

    def test_unsubscribe(self):
        eb = EventBus()
        received = []

        def cb(**kw):
            received.append(kw)

        eb.subscribe("test", cb)
        eb.unsubscribe("test", cb)
        eb.emit("test", x=1)

        assert len(received) == 0

    def test_different_event_types(self):
        eb = EventBus()
        r_a, r_b = [], []

        eb.subscribe("alpha", lambda **kw: r_a.append(kw))
        eb.subscribe("beta", lambda **kw: r_b.append(kw))
        eb.emit("alpha", x=1)

        assert len(r_a) == 1
        assert len(r_b) == 0

    def test_subscriber_exception_does_not_crash(self):
        eb = EventBus()
        received = []

        def _failing(**kw):
            raise RuntimeError("boom")

        eb.subscribe("test", _failing)
        eb.subscribe("test", lambda **kw: received.append(kw))
        eb.emit("test", x=1)

        assert len(received) == 1  # second subscriber still got it

    def test_recent_events(self):
        eb = EventBus()
        eb.emit("test", a=1)
        eb.emit("test", b=2)
        eb.emit("test", c=3)

        recent = eb.recent_events(2)
        assert len(recent) == 2
        assert recent[-1]["data"]["c"] == 3

    def test_event_log_auto_prunes(self):
        eb = EventBus()
        for i in range(6000):
            eb.emit("fill", index=i)
        assert len(eb._event_log) <= 5000

    def test_thread_safety(self):
        eb = EventBus()
        received = []

        eb.subscribe("th", lambda **kw: received.append(kw))

        def emit_batch(start, count):
            for i in range(start, start + count):
                eb.emit("th", index=i)

        threads = []
        for i in range(0, 200, 50):
            t = threading.Thread(target=emit_batch, args=(i, 50))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        assert len(received) == 200
        indices = sorted(r["index"] for r in received)
        assert indices == list(range(200))

"""Tests for tools/task_queue.py."""
from tools.task_queue import TaskQueue, get_task_queue, reset_task_queue


class TestTaskQueue:
    def teardown_method(self):
        reset_task_queue()

    def test_register_and_execute(self):
        tq = TaskQueue()
        results = []
        tq.register_handler("greet", lambda name: results.append(f"hello {name}"))
        tq.enqueue("default", "greet", "world")
        assert results == ["hello world"]

    def test_handler_not_found_returns_none(self):
        tq = TaskQueue()
        result = tq.enqueue("default", "missing")
        assert result is None

    def test_exception_in_handler_logged(self):
        tq = TaskQueue()
        tq.register_handler("bad", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        result = tq.enqueue("default", "bad")
        assert result is None

    def test_multiple_handlers(self):
        tq = TaskQueue()
        results = []
        tq.register_handler("a", lambda: results.append("a"))
        tq.register_handler("b", lambda: results.append("b"))
        tq.enqueue("default", "a")
        tq.enqueue("default", "b")
        assert results == ["a", "b"]

    def test_singleton(self):
        reset_task_queue()
        tq1 = get_task_queue()
        tq2 = get_task_queue()
        assert tq1 is tq2

    def test_reset_creates_new(self):
        tq1 = get_task_queue()
        reset_task_queue()
        tq2 = get_task_queue()
        assert tq1 is not tq2

    def test_stop_all_clears_workers(self):
        tq = TaskQueue()
        tq.register_handler("noop", lambda: None)
        tq.start_worker("default", poll_interval=0.1)
        assert "default" in tq._workers
        tq.stop_all()
        assert not tq._running_event.is_set()

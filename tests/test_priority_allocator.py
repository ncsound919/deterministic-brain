import time
from reasoning.priority_engine import PriorityEngine
from orchestration.resource_allocator import ResourceAllocator


def test_priority_engine_basic():
    pe = PriorityEngine()
    candidates = [
        {"id": "a", "arm_id": "a", "text": "send welcome email"},
        {"id": "b", "arm_id": "b", "text": "send discount sms"},
        {"id": "c", "arm_id": "c", "text": "show in-app nudge"},
    ]
    ctx = {"query": "welcome email"}
    scored = pe.score_candidates(candidates, ctx)
    assert isinstance(scored, list)
    assert len(scored) == 3
    # top candidate should be one of provided ids
    assert scored[0][0]["id"] in {"a","b","c"}


def test_resource_allocator_allocate_release():
    ra = ResourceAllocator(max_units=2)
    assert ra.get_available() == 2
    ok = ra.allocate("t1", units=1, timeout=0.1)
    assert ok
    assert ra.get_available() == 1
    ok2 = ra.allocate("t2", units=1, timeout=0.1)
    assert ok2
    assert ra.get_available() == 0
    # third allocation should timeout/fail
    ok3 = ra.allocate("t3", units=1, timeout=0.05)
    assert not ok3
    ra.release("t1", units=1)
    assert ra.get_available() == 1
    ra.release("t2", units=1)
    assert ra.get_available() == 2

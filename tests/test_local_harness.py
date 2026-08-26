"""Tests for the local model harness (tools/local_harness.py)."""

import json
import pytest

from tools.local_harness import (
    EpisodicStore,
    SemanticStore,
    RunningSummaries,
    EcosystemContext,
    LocalModelHarness,
    get_harness,
    reset_harness,
)


@pytest.fixture()
def tmp_memory(tmp_path):
    """Redirect harness memory stores to a temp dir."""
    h = LocalModelHarness()
    h.episodic = EpisodicStore(path=tmp_path / "episodic.jsonl")
    h.semantic = SemanticStore(path=tmp_path / "semantic.json")
    h.summaries = RunningSummaries(path=tmp_path / "summaries.json")
    return h


class TestEpisodicStore:
    def test_add_and_recent(self, tmp_path):
        store = EpisodicStore(path=tmp_path / "ep.jsonl")
        ep_id = store.add("question", "answer", role="chat", metadata={"thread": "t1"})
        assert ep_id
        recent = store.recent(limit=10)
        assert len(recent) == 1
        assert recent[0]["prompt"] == "question"
        assert recent[0]["result"] == "answer"
        assert recent[0]["role"] == "chat"

    def test_count(self, tmp_path):
        store = EpisodicStore(path=tmp_path / "ep.jsonl")
        for i in range(3):
            store.add(f"q{i}", f"a{i}")
        assert store.count() == 3

    def test_search_keyword(self, tmp_path):
        store = EpisodicStore(path=tmp_path / "ep.jsonl")
        store.add("the scheduler job failed three times", "escalated to repair team")
        store.add("revenue pulse", "$0 settled today")
        hits = store.search_keyword("scheduler failed", top_k=5)
        assert len(hits) >= 1
        assert "scheduler" in hits[0]["prompt"]


class TestSemanticStore:
    def test_add_and_recall(self, tmp_path):
        store = SemanticStore(path=tmp_path / "semantic.json")
        store.add("Ollama is the primary local backend", category="infra")
        store.add("Revenue target is $33k/month", category="finance")
        hits = store.recall("revenue target", top_k=5)
        assert any("33k" in f.get("fact", "") for f in hits)

    def test_add_many(self, tmp_path):
        store = SemanticStore(path=tmp_path / "semantic.json")
        added = store.add_many([
            {"fact": "fact one", "category": "a"},
            {"fact": "fact two", "category": "b"},
            {"fact": "", "category": "c"},  # empty should be skipped
        ])
        assert added == 2
        assert len(store.all()) == 2


class TestRunningSummaries:
    def test_update_get(self, tmp_path):
        store = RunningSummaries(path=tmp_path / "summaries.json")
        store.update("t1", "summary v1", 1)
        store.update("t1", "summary v2", 2)
        assert store.get("t1") == "summary v2"


class TestEcosystemContext:
    def test_append_lesson_shape(self, tmp_path):
        ctx = EcosystemContext(draymond_dir=tmp_path)
        ok = ctx.append_lesson("test-pattern", "test lesson", agent_id="deterministic-brain")
        assert ok
        data = json.loads((tmp_path / "learning-lessons.json").read_text(encoding="utf-8"))
        assert data["lessons"][0]["id"].startswith("ls_")
        assert data["lessons"][0]["evidenceCount"] == 1
        # Append again → evidence bumps, not duplicated
        ctx.append_lesson("test-pattern", "test lesson", agent_id="deterministic-brain")
        data = json.loads((tmp_path / "learning-lessons.json").read_text(encoding="utf-8"))
        assert len(data["lessons"]) == 1
        assert data["lessons"][0]["evidenceCount"] == 2

    def test_append_recap(self, tmp_path):
        ctx = EcosystemContext(draymond_dir=tmp_path)
        ok = ctx.append_recap("consolidation", "summary text", {"k": "v"})
        assert ok
        data = json.loads((tmp_path / "recaps.json").read_text(encoding="utf-8"))
        assert data["recaps"][0]["phase"] == "consolidation"
        assert data["recaps"][0]["summary"] == "summary text"

    def test_missing_files_are_safe(self, tmp_path):
        ctx = EcosystemContext(draymond_dir=tmp_path)
        # Must never raise; identity comes from the real brain soul, the rest
        # degrades to empty when .draymond files are absent.
        text = ctx.compact_context()
        assert isinstance(text, str)
        assert ctx.lessons() == []
        assert ctx.goals() == []


class TestHarnessMethods:
    def test_remember_and_recall(self, tmp_memory):
        tmp_memory.remember("lead from marketing", "qualified, follow up in 24h", role="sales")
        tmp_memory.remember("scheduler failure", "escalated to repair", role="ops")
        memories = tmp_memory.recall("marketing lead", top_k=5)
        assert any("marketing" in m for m in memories)

    def test_classify_fallback_without_model(self, tmp_memory):
        # No live backend → classify should still return a label via fuzzy match
        tmp_memory._svc = _NoModelService()
        result = tmp_memory.classify("the scheduler job failed and was escalated", ["coding", "ops", "marketing"])
        assert result.get("label") in ("coding", "ops", "marketing")

    def test_memory_only_answer_when_offline(self, tmp_memory):
        tmp_memory.remember("revenue", "$1000", role="finance")
        tmp_memory._svc = _NoModelService()
        answer = tmp_memory._memory_only_answer("what about revenue?", "default")
        assert "[memory-only]" in answer

    def test_status_shape(self, tmp_memory):
        tmp_memory._svc = _NoModelService()
        status = tmp_memory.status()
        assert status["harness"] == "local_model"
        assert "memory" in status
        assert "ecosystem" in status

    def test_fast_reason_uses_fast_tier(self, tmp_memory):
        calls = []

        class FastService:
            def is_available(self):
                return True

            def chat(self, system, user, max_tokens=2048, fast=False):
                calls.append({"system": system, "fast": fast})
                return "- Repair the monitor first."

        tmp_memory._svc = FastService()
        answer = tmp_memory.fast_reason("a monitor is down")
        assert answer == "- Repair the monitor first."
        assert calls and calls[0]["fast"] is True
        # Records an episode
        assert tmp_memory.episodic.count() >= 1

    def test_fast_reason_empty_when_offline(self, tmp_memory):
        tmp_memory._svc = _NoModelService()
        assert tmp_memory.fast_reason("test") == ""


class TestMemoryEvolution:
    """OpenViking-style self-evolving memory (decay, promote, derive skills)."""

    def test_promote_bumps_confidence(self, tmp_path):
        store = SemanticStore(path=tmp_path / "semantic.json")
        fid = store.add("fact one", category="a", confidence=0.6)
        store.promote(fid)
        store.promote(fid)
        assert any(abs(f["confidence"] - 0.7) < 0.001 for f in store.all())

    def test_decay_prunes_stale_low_confidence(self, tmp_path):
        store = SemanticStore(path=tmp_path / "semantic.json")
        store.add("durable high-conf fact", category="a", confidence=0.95)
        store.add("weak fact", category="b", confidence=0.1)
        removed = store.decay(stale_days=0, min_confidence=0.5)
        assert removed >= 1
        remaining = [f["fact"] for f in store.all()]
        assert "durable high-conf fact" in remaining

    def test_derive_skills_picks_howto_facts(self, tmp_path):
        h = LocalModelHarness()
        h.semantic = SemanticStore(path=tmp_path / "semantic.json")
        h.ecosystem = EcosystemContext(draymond_dir=tmp_path)
        h.semantic.add("Always verify config after editing", category="ops", confidence=0.95)
        h.semantic.add("revenue was 0", category="finance", confidence=0.9)  # not how-to
        skills = h.derive_skills(min_confidence=0.7)
        assert any("verify config" in s for s in skills)
        assert not any("revenue was 0" in s for s in skills)

    def test_derive_skills_writes_to_draymond(self, tmp_path):
        h = LocalModelHarness()
        h.semantic = SemanticStore(path=tmp_path / "semantic.json")
        h.ecosystem = EcosystemContext(draymond_dir=tmp_path)
        h.semantic.add("Run the health check before deploy", category="ops", confidence=0.9)
        h.derive_skills(min_confidence=0.7)
        data = json.loads((tmp_path / "learning-lessons.json").read_text(encoding="utf-8"))
        assert any(l["pattern"] == "derived-skill" for l in data["lessons"])


class _NoModelService:
    def is_available(self):
        return False

    def status(self):
        return {"available": False}

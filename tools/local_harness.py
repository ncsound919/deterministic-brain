"""Local Model Harness — memory, ecosystem awareness, full capability surface.

Wraps the unified local model service (`tools.local_model`) with three layers
so the small model becomes a first-class, self-improving citizen of the
Overlay365 fleet:

  1. Karpathy-style memory extension
     - Episodic store  : append-only JSONL log of every interaction
     - Semantic store  : distilled facts / patterns (written by the model)
     - Procedural store: lessons & how-to knowledge (synced to .draymond)
     - Running summary : recursive conversation compression per thread
     - Recall          : retrieval-augmented memory injection into prompts
     - Consolidate     : "sleep-time compute" — distill episodes → semantics

  2. Ecosystem awareness
     - Loads .soul.yaml identity
     - Reads .draymond/ brain state (lessons, recaps, goals, treasury)
     - Injects a compact fleet-context block into prompts
     - Writes lessons + recaps back (append-only, shape-preserving)

  3. Full local-model capability surface
     - chat / generate_text / generate_json / complete_with_cot (memory-aware)
     - reason (CoT), classify (JSON), summarize (recursive), extract (JSON)
     - status() → backend + memory + fleet health for the dashboard / fleet

Everything degrades gracefully: no local backend, missing files, bad JSON —
the harness never raises, it returns the best deterministic answer it can.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from config import cfg

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BRAIN_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .draymond is a sibling of agents/deterministic-brain under Draymond-Orchestrator
DRAYMOND_DIR = Path(os.getenv("DRAYMOND_REGISTRY_DIR", BRAIN_ROOT.parent.parent / ".draymond"))

MEMORY_DIR = BRAIN_ROOT / ".local_memory"
EPISODIC_PATH = MEMORY_DIR / "episodic.jsonl"
SEMANTIC_PATH = MEMORY_DIR / "semantic.json"
SUMMARY_PATH = MEMORY_DIR / "summaries.json"
RUNNING_SUMMARY_THREADS = 32
DEFAULT_RECALL_TOP_K = 5


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Memory stores (Karpathy layers)
# ---------------------------------------------------------------------------

class EpisodicStore:
    """Append-only JSONL of every interaction (episodic memory)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or EPISODIC_PATH)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, prompt: str, result: str, role: str = "task", metadata: Optional[Dict] = None) -> str:
        """Record one episode. Returns an episode id."""
        episode_id = str(uuid.uuid4())[:12]
        entry = {
            "id": episode_id,
            "ts": _utcnow(),
            "role": role,
            "prompt": (prompt or "")[:8000],
            "result": (result or "")[:8000],
            "meta": metadata or {},
        }
        with self._lock:
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError as e:
                logger.warning("episodic write failed: %s", e)
        return episode_id

    def recent(self, limit: int = 50) -> List[Dict]:
        """Newest-first list of recent episodes."""
        if not self.path.exists():
            return []
        entries: List[Dict] = []
        try:
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return entries[-limit:][::-1]

    def search_keyword(self, query: str, top_k: int = DEFAULT_RECALL_TOP_K) -> List[Dict]:
        """Cheap lexical recall over recent episodes (TF-style scoring)."""
        tokens = [t.lower() for t in re.findall(r"\w+", query)]
        if not tokens:
            return []
        scored = []
        for ep in self.recent(limit=400):
            hay = f"{ep.get('prompt','')} {ep.get('result','')}".lower()
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, ep))
        scored.sort(key=lambda x: -x[0])
        return [ep for _, ep in scored[:top_k]]

    def count(self) -> int:
        if not self.path.exists():
            return 0
        return sum(1 for _ in open(self.path, encoding="utf-8"))


class SemanticStore:
    """Distilled facts/patterns (semantic memory) — a JSON index."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or SEMANTIC_PATH)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> List[Dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("facts", [])
        except (json.JSONDecodeError, OSError):
            return []
        return []

    def add(self, fact: str, category: str = "general", source: str = "local-model", confidence: float = 1.0) -> str:
        fact_id = str(uuid.uuid4())[:12]
        entry = {
            "id": fact_id,
            "fact": (fact or "")[:2000],
            "category": category,
            "source": source,
            "confidence": min(1.0, max(0.0, confidence)),
            "ts": _utcnow(),
        }
        with self._lock:
            facts = self._load()
            facts.append(entry)
            self._write(facts)
        return fact_id

    def add_many(self, facts: List[Dict]) -> int:
        with self._lock:
            all_facts = self._load()
            added = 0
            for f in facts:
                entry = {
                    "id": str(uuid.uuid4())[:12],
                    "fact": (f.get("fact") or f.get("summary") or "")[:2000],
                    "category": f.get("category", "general"),
                    "source": f.get("source", "local-model"),
                    "confidence": min(1.0, max(0.0, float(f.get("confidence", 1.0)))),
                    "ts": _utcnow(),
                }
                if entry["fact"]:
                    all_facts.append(entry)
                    added += 1
            self._write(all_facts)
        return added

    def recall(self, query: str, top_k: int = DEFAULT_RECALL_TOP_K) -> List[Dict]:
        tokens = [t.lower() for t in re.findall(r"\w+", query)]
        facts = self._load()
        if not tokens:
            return facts[-top_k:][::-1]
        scored = []
        for f in facts:
            hay = f"{f.get('fact','')} {f.get('category','')}".lower()
            score = sum(1 for t in tokens if t in hay)
            if score:
                scored.append((score, f))
        scored.sort(key=lambda x: -x[0])
        return [f for _, f in scored[:top_k]]

    def all(self) -> List[Dict]:
        return self._load()

    def promote(self, fact_id: str) -> None:
        """Bump a fact's confidence/recency when it's recalled — self-evolving
        memory: frequently-reused facts become more durable (OpenViking-style)."""
        with self._lock:
            facts = self._load()
            for f in facts:
                if f.get("id") == fact_id:
                    f["confidence"] = min(1.0, float(f.get("confidence", 1.0)) + 0.05)
                    f["ts"] = _utcnow()
                    break
            self._write(facts)

    def decay(self, stale_days: int = 30, min_confidence: float = 0.15) -> int:
        """Decay unused semantic facts over time and prune stale/low-confidence
        ones — memory consolidation so the store stays tight and relevant."""
        now = time.time()
        cutoff = now - stale_days * 86400
        with self._lock:
            facts = self._load()
            kept = []
            removed = 0
            for f in facts:
                try:
                    age = now - datetime.fromisoformat(f.get("ts", "")).timestamp()
                except Exception:
                    age = 0
                conf = float(f.get("confidence", 1.0))
                # Age-decay confidence, prune if it falls below the floor.
                decayed = conf * (0.9 ** (age / (7 * 86400))) if age > cutoff else conf
                if age <= cutoff and decayed < min_confidence:
                    removed += 1
                    continue
                f["confidence"] = round(decayed, 3)
                kept.append(f)
            self._write(kept)
        return removed

    def _write(self, facts: List[Dict]) -> None:
        try:
            self.path.write_text(
                json.dumps({"facts": facts, "updatedAt": _utcnow()}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("semantic write failed: %s", e)


class RunningSummaries:
    """Recursive conversation compression per thread (Karpathy running summary)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or SUMMARY_PATH)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, Dict]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get(self, thread: str) -> str:
        return self._load().get(thread, {}).get("summary", "")

    def update(self, thread: str, summary: str, turn_count: int) -> None:
        with self._lock:
            data = self._load()
            data[thread] = {"summary": summary, "turns": turn_count, "updatedAt": _utcnow()}
            # Keep the map bounded (LRU-ish: drop oldest by updatedAt)
            if len(data) > RUNNING_SUMMARY_THREADS:
                oldest = sorted(data, key=lambda k: data[k].get("updatedAt", ""))[0]
                data.pop(oldest, None)
            try:
                self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except OSError as e:
                logger.warning("summary write failed: %s", e)


# ---------------------------------------------------------------------------
# Ecosystem awareness (.draymond + .soul.yaml)
# ---------------------------------------------------------------------------

class EcosystemContext:
    """Reads fleet brain state so the local model operates ecosystem-aware."""

    def __init__(self, draymond_dir: Path | None = None) -> None:
        self.dir = Path(draymond_dir or DRAYMOND_DIR)

    def soul_identity(self) -> Dict:
        try:
            from brain.soul import get_soul
            s = get_soul()
            return {"name": s.identity.get("name", ""), "role": s.identity.get("role", ""),
                    "mission": s.agenda.get("mission", "")[:200]}
        except Exception:
            pass
        # Fall back to raw yaml read
        try:
            import yaml
            p = BRAIN_ROOT / ".soul.yaml"
            if p.exists():
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                return {"name": data.get("identity", {}).get("name", ""),
                        "role": data.get("identity", {}).get("role", ""),
                        "mission": (data.get("agenda", {}) or {}).get("mission", "")[:200]}
        except Exception:
            pass
        return {}

    def _read_json(self, name: str) -> Dict:
        p = self.dir / name
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def lessons(self, limit: int = 5) -> List[str]:
        data = self._read_json("learning-lessons.json")
        lessons = data.get("lessons", []) if isinstance(data, dict) else []
        out = []
        for l in lessons[:limit]:
            pat = l.get("pattern", "")
            les = l.get("lesson", "")
            out.append(f"[{l.get('evidenceCount', 0)}x] {pat}: {les[:140]}")
        return out

    def goals(self, limit: int = 4) -> List[str]:
        data = self._read_json("system-goals.json")
        goals = data.get("goals", data.get("system_goals", [])) if isinstance(data, dict) else []
        out = []
        for g in goals[:limit]:
            if isinstance(g, dict):
                out.append(f"{g.get('title', g.get('domain', ''))} ({g.get('status', '')})")
            else:
                out.append(str(g))
        return out

    def treasury(self) -> Dict:
        data = self._read_json("treasury.json")
        return {"revenue_cents": data.get("revenueCents", 0),
                "target_cents": data.get("targetCents", 3300000),
                "last_pulse": data.get("lastPulseAt", "")}

    def recaps(self, limit: int = 3) -> List[str]:
        data = self._read_json("recaps.json")
        recs = data.get("recaps", []) if isinstance(data, dict) else []
        out = []
        for r in recs[-limit:][::-1]:
            summary = r.get("summary", "")
            phase = r.get("phase", "")
            out.append(f"[{phase}] {summary[:160]}")
        return out

    def compact_context(self, max_lines: int = 8) -> str:
        """A short, model-friendly fleet state block injected into prompts.

        Deliberately small: on this CPU class (~9 t/s prefill) every token in
        the prompt costs real latency per call, and single-turn chats defeat
        KV caching anyway. Memoized on .draymond file mtimes so the block is
        byte-identical between state changes.
        """
        cache_key = self._state_mtime_key()
        if cache_key == getattr(self, "_ctx_cache_key", None):
            return getattr(self, "_ctx_cache", "")
        lines = []
        identity = self.soul_identity()
        if identity.get("name"):
            lines.append(f"Identity: {identity.get('name')} ({identity.get('role')})")
        if identity.get("mission"):
            lines.append(f"Mission: {identity.get('mission')[:120]}")
        t = self.treasury()
        rev = t.get("revenue_cents", 0) / 100
        target = t.get("target_cents", 3300000) / 100
        lines.append(f"Revenue: ${rev:,.2f} / target ${target:,.2f}/mo")
        goals = self.goals(limit=3)
        if goals:
            lines.append("Goals: " + " | ".join(goals))
        lessons = self.lessons(limit=1)
        if lessons:
            lines.append("Lesson: " + lessons[0])
        recaps = self.recaps(limit=1)
        if recaps:
            lines.append("Recap: " + recaps[0])
        text = "\n".join(lines[:max_lines])
        self._ctx_cache_key = cache_key
        self._ctx_cache = text
        return text

    def _state_mtime_key(self) -> str:
        """Hash of the mtimes/sizes of the .draymond files we read."""
        parts = []
        for name in ("treasury.json", "learning-lessons.json", "recaps.json", "system-goals.json"):
            p = self.dir / name
            try:
                st = p.stat()
                parts.append(f"{name}:{st.st_mtime_ns}:{st.st_size}")
            except OSError:
                parts.append(f"{name}:missing")
        return "|".join(parts)

    def append_lesson(self, pattern: str, lesson: str, agent_id: str = "deterministic-brain") -> bool:
        """Append a lesson to .draymond/learning-lessons.json (shape-preserving)."""
        p = self.dir / "learning-lessons.json"
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
            else:
                data = {"lessons": []}
            if not isinstance(data, dict):
                data = {"lessons": []}
            data.setdefault("lessons", [])
            key = re.sub(r"[^a-z0-9]+", "", f"{agent_id}{pattern}".lower())[:40] or "ls"
            lesson_id = f"ls_{key}"
            # de-dup / bump evidenceCount
            replaced = False
            for l in data["lessons"]:
                if l.get("id") == lesson_id:
                    l["lesson"] = lesson
                    l["evidenceCount"] = int(l.get("evidenceCount", 1)) + 1
                    l["lastSeen"] = _utcnow()
                    replaced = True
                    break
            if not replaced:
                data["lessons"].append({
                    "id": lesson_id,
                    "agentId": agent_id,
                    "pattern": pattern,
                    "lesson": lesson,
                    "evidenceCount": 1,
                    "lastSeen": _utcnow(),
                })
            data["updatedAt"] = _utcnow()
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError as e:
            logger.warning("lesson append failed: %s", e)
            return False

    def append_recap(self, phase: str, summary: str, sections: Optional[Dict] = None) -> bool:
        p = self.dir / "recaps.json"
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
            else:
                data = {"recaps": []}
            if not isinstance(data, dict):
                data = {"recaps": []}
            data.setdefault("recaps", [])
            data["recaps"].append({
                "phase": phase,
                "generatedAt": _utcnow(),
                "sections": sections or {},
                "summary": summary,
            })
            if len(data["recaps"]) > 500:
                data["recaps"] = data["recaps"][-500:]
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except OSError as e:
            logger.warning("recap append failed: %s", e)
            return False


# ---------------------------------------------------------------------------
# The Harness
# ---------------------------------------------------------------------------

class LocalModelHarness:
    """Memory-aware, ecosystem-aware facade over the unified local model."""

    def __init__(self) -> None:
        self._svc = None
        self.episodic = EpisodicStore()
        self.semantic = SemanticStore()
        self.summaries = RunningSummaries()
        self.ecosystem = EcosystemContext()

    # ---- service access ----
    def _service(self):
        if self._svc is None:
            from tools.local_model import get_local_model
            self._svc = get_local_model()
        return self._svc

    def reset(self) -> None:
        self._svc = None

    def is_available(self) -> bool:
        try:
            return self._service().is_available()
        except Exception:
            return False

    def warm(self) -> bool:
        """Preload the local model so the first real call isn't slow."""
        try:
            return bool(self._service().warm())
        except Exception:
            return False

    def supports_vision(self) -> bool:
        try:
            return bool(self._service().supports_vision())
        except Exception:
            return False

    def analyze_image(self, prompt: str, image_path: str, max_tokens: int = 512) -> str:
        """Vision: analyse an image with the local vision model."""
        try:
            return self._service().chat_with_image(prompt, image_path, max_tokens=max_tokens)
        except Exception:
            return ""

    def call_tools(self, prompt: str, tools: List[Dict[str, Any]], max_tokens: int = 256) -> Dict[str, Any]:
        """Tool calling via the local model."""
        try:
            return self._service().call_tools(prompt, tools, max_tokens=max_tokens)
        except Exception:
            return {}

    # ---- capability surface (memory-aware) ----

    def _context_block(self, query: str, include_ecosystem: bool = True, recall: bool = True) -> str:
        """Assemble injected context: ecosystem state + recalled memories."""
        parts = []
        if include_ecosystem:
            eco = self.ecosystem.compact_context()
            if eco:
                parts.append(f"[FLEET CONTEXT]\n{eco}")
        if recall:
            memories = self.recall(query, top_k=DEFAULT_RECALL_TOP_K)
            if memories:
                mem_txt = "\n".join(f"- {m}" for m in memories)
                parts.append(f"[MEMORY]\n{mem_txt}")
        return "\n\n".join(parts)

    def chat(self, system: str, user: str, max_tokens: int = 2048,
             thread: str = "default", with_memory: bool = True,
             fast: bool = True) -> str:
        """Chat with fleet + memory context injected, then log the episode.

        The fleet-context block is memoized (stable prefix → KV cache hits),
        so it is appended to the SYSTEM prompt. Only the lightweight lexical
        recall travels with the user message. Interactive chat defaults to the
        fast tier (LOCAL_MODEL_FAST) — benchmarked ~16x faster on this CPU.
        """
        svc = self._service()
        if not svc.is_available():
            return self._memory_only_answer(user, thread)
        # Stable, memoized fleet context in the system prompt.
        eco = self.ecosystem.compact_context()
        system_block = f"{system}\n\n[FLEET CONTEXT]\n{eco}" if eco else system
        # Query-specific recall appended to the user turn (small, volatile).
        memories = self.recall(user, top_k=2) if with_memory else []
        prompt = user
        if memories:
            prompt = f"[MEMORY]\n" + "\n".join(f"- {m}" for m in memories) + f"\n\n{user}"
        running = self.summaries.get(thread)
        full_system = f"{system_block}\n\nThread summary so far:\n{running}" if running else system_block
        result = svc.chat(full_system, prompt, max_tokens=max_tokens, fast=fast)
        if result:
            self.episodic.add(user, result, role="chat", metadata={"thread": thread})
            self._maybe_compress(thread, user, result)
        return result

    def generate_text(self, prompt: str, system: str | None = None, max_tokens: int = 2048,
                      thread: str = "default", with_memory: bool = True) -> str:
        svc = self._service()
        if not svc.is_available():
            return ""
        ctx = self._context_block(prompt) if with_memory else ""
        full = f"{ctx}\n\n{prompt}" if ctx else prompt
        result = svc.generate_text(full, system=system, max_tokens=max_tokens)
        if result:
            self.episodic.add(prompt, result, role="text", metadata={"thread": thread})
        return result

    def generate_json(self, prompt: str, max_tokens: int = 2048,
                      thread: str = "default", with_memory: bool = True,
                      fast: bool = False) -> Dict[str, Any]:
        svc = self._service()
        if not svc.is_available():
            return {}
        ctx = self._context_block(prompt) if with_memory else ""
        full = f"{ctx}\n\n{prompt}" if ctx else prompt
        result = svc.generate_json(full, max_tokens=max_tokens, fast=fast)
        if result:
            self.episodic.add(prompt, json.dumps(result)[:2000], role="json", metadata={"thread": thread})
        return result

    def reason(self, problem: str, max_tokens: int = 2048, thread: str = "default") -> Tuple[str, str]:
        """Chain-of-thought reasoning with memory context. Returns (scratchpad, answer)."""
        svc = self._service()
        if not svc.is_available():
            return "", ""
        ctx = self._context_block(problem)
        prompt = f"{ctx}\n\n{problem}" if ctx else problem
        scratch, answer = svc.complete_with_cot(
            "You are a precise reasoning engine. Think step by step, then answer.",
            prompt, max_tokens=max_tokens,
        )
        if answer:
            self.episodic.add(problem, answer, role="reason", metadata={"thread": thread})
        return scratch, answer

    def fast_reason(self, problem: str, max_tokens: int = 300, thread: str = "default") -> str:
        """Fast, direct ops reasoning on the light tier (no long CoT scratchpad).

        Optimised for time-boxed triage (Draymond's 30s budget): uses the fast
        model with thinking disabled for a concise answer, not a lengthy
        scratchpad. Returns the answer string.
        """
        svc = self._service()
        if not svc.is_available():
            return ""
        answer = svc.chat(
            "You are a concise operations triage assistant. Answer in 2-4 short bullets, no preamble, no step-by-step.",
            problem, max_tokens=max_tokens, fast=True,
        )
        if answer:
            self.episodic.add(problem, answer, role="fast_reason", metadata={"thread": thread})
        return answer

    def briefing(self, focus: str = "fleet ops", max_tokens: int = 400) -> str:
        """Generate a concise local-model briefing from current fleet state.

        Uses the fast tier (cheap, on-device) to turn live ecosystem context
        into a short ops briefing for reports / schedule kickoffs.
        """
        svc = self._service()
        if not svc.is_available():
            return ""
        eco = self.ecosystem.compact_context()
        prompt = (
            f"Write a concise {focus} briefing from this fleet state. "
            "3-5 tight bullets: what's working, what needs attention, one next action.\n\n"
            f"Fleet state:\n{eco}"
        )
        return svc.chat(
            "You are the fleet ops reporter. Be concrete, specific, no fluff.",
            prompt, max_tokens=max_tokens, fast=True,
        )

    def classify(self, text: str, labels: List[str], thread: str = "default",
                 fast: bool = True) -> Dict[str, Any]:
        """Classify text into one of the given labels. Returns JSON."""
        label_json = json.dumps(labels)
        prompt = (
            f"Classify the following text into exactly one of these labels: {label_json}\n"
            f"Respond ONLY with JSON: {{\"label\": \"<one label>\", \"confidence\": 0.0}}\n\n"
            f"Text:\n{text}"
        )
        result = self.generate_json(prompt, thread=thread, fast=fast)
        if result.get("label") not in labels:
            # fallback: fuzzy match to a known label
            best = labels[0] if labels else ""
            best_score = 0
            for lab in labels:
                s = sum(1 for tok in re.findall(r"\w+", lab.lower()) if tok in text.lower())
                if s > best_score:
                    best_score = s
                    best = lab
            result = {"label": best, "confidence": 0.3}
        return result

    def summarize(self, text: str, max_tokens: int = 512) -> str:
        """One-shot recursive summarization via the local model."""
        svc = self._service()
        if not svc.is_available():
            return text[:512]
        prompt = (
            "Summarize the following content in 3-5 concise bullet points, "
            "capturing the key facts and decisions. Preserve numbers.\n\n" + text[:4000]
        )
        summary = svc.chat("You are a precise summarizer.", prompt, max_tokens=max_tokens)
        return summary or text[:512]

    def extract(self, text: str, schema: Dict[str, Any], thread: str = "default") -> Dict[str, Any]:
        """Extract fields matching a JSON schema."""
        schema_json = json.dumps(schema, indent=2)
        prompt = (
            f"Extract a JSON object matching this schema:\n{schema_json}\n\n"
            f"Respond ONLY with valid JSON.\n\nText:\n{text}"
        )
        return self.generate_json(prompt, thread=thread)

    # ---- memory API (Karpathy methods) ----

    def remember(self, prompt: str, result: str, role: str = "task", metadata: Optional[Dict] = None) -> str:
        """Write an episode to episodic memory. Call this after any significant interaction."""
        return self.episodic.add(prompt, result, role=role, metadata=metadata)

    def recall(self, query: str, top_k: int = DEFAULT_RECALL_TOP_K) -> List[str]:
        """Retrieve relevant memories: semantic facts + episodic (+ optional
        knowledge bank / vector memory).

        Only fast, dependency-free stores run by default (JSON/lexical, no
        model loading). Knowledge-bank and vector search load heavy embedding
        models, so they are opt-in via LOCAL_HARNESS_VECTOR=1.
        """
        out: List[str] = []
        seen = set()

        def push(text: str):
            if text and text[:80] not in seen:
                seen.add(text[:80])
                out.append(text)

        for f in self.semantic.recall(query, top_k=top_k):
            # Self-evolving memory: recalling a fact strengthens it.
            self.semantic.promote(f.get("id", ""))
            push(f"[fact/{f.get('category','general')}] {f.get('fact','')}")
        for ep in self.episodic.search_keyword(query, top_k=2):
            push(f"[episode] Q: {ep.get('prompt','')[:200]} -> A: {ep.get('result','')[:200]}")
        if os.getenv("LOCAL_HARNESS_VECTOR", "0") == "1":
            self._heavy_recall(query, push)
        return out[:top_k]

    def _heavy_recall(self, query: str, push) -> None:
        """Heavy retrieval (embedding models) — opt-in only, attempted once."""
        if getattr(self, "_heavy_tried", False):
            return
        self._heavy_tried = True
        try:
            from knowledge.bank import get_knowledge_bank
            kb = get_knowledge_bank()
            for frag, score in kb.query(query, top_k=2):
                push(f"[kb/{frag.category}] {frag.content[:250]}")
        except Exception:
            pass
        try:
            from vector_memory import vector_memory
            for r in vector_memory.search_knowledge(query, n_results=2):
                push(f"[vector] {r.get('content','')[:250]}")
        except Exception:
            pass

    def consolidate(self, max_episodes: int = 8) -> Dict[str, Any]:
        """Sleep-time compute: distill recent episodes into semantic facts + a lesson.

        Runs the local model over the newest episodes and writes distilled
        facts into the semantic store and one lesson into .draymond.
        Designed as a background/scheduled job (the local model is slower
        than remote APIs) — call via cron or the /local/harness/consolidate
        endpoint, not on the interactive hot path.
        """
        svc = self._service()
        episodes = self.episodic.recent(limit=max_episodes)
        if not svc.is_available():
            return {"ok": False, "reason": "no local backend", "processed": 0}

        batch = "\n\n".join(
            f"EP{i}: {ep.get('prompt','')[:200]}\nOUT: {ep.get('result','')[:150]}"
            for i, ep in enumerate(episodes)
        )
        prompt = (
            "From these interactions, extract at most 2 durable, reusable facts "
            "and one recurring pattern (or empty string).\n"
            "Respond ONLY with JSON: {\"facts\": [{\"fact\": \"...\", \"category\": \"...\"}], "
            "\"pattern\": \"...\"}\n\n"
            f"Interactions:\n{batch}"
        )
        result = svc.generate_json(prompt, max_tokens=450)
        added = 0
        facts = result.get("facts", []) if isinstance(result, dict) else []
        if facts:
            added = self.semantic.add_many(facts)
        pattern = (result.get("pattern") or "").strip() if isinstance(result, dict) else ""
        if pattern:
            self.ecosystem.append_lesson(pattern="local-model consolidation",
                                         lesson=pattern[:400])
        summary = f"Consolidated {len(episodes)} episodes -> {added} facts" + (f"; pattern: {pattern[:60]}" if pattern else "")
        self.ecosystem.append_recap(phase="consolidation", summary=summary)
        return {"ok": True, "processed": len(episodes), "facts_added": added, "pattern": pattern or None}

    def evolve_memory(self, stale_days: int = 30, min_confidence: float = 0.15) -> Dict[str, Any]:
        """Self-evolving memory pass (OpenViking-style): decay + prune stale
        semantic facts so the store stays tight, then derive reusable skills
        from high-confidence facts. Call periodically (e.g. with consolidate)."""
        pruned = self.semantic.decay(stale_days=stale_days, min_confidence=min_confidence)
        skills = self.derive_skills()
        return {"pruned_facts": pruned, "skills_derived": skills}

    def derive_skills(self, min_confidence: float = 0.7, max_skills: int = 5) -> List[str]:
        """Promote high-confidence, action-oriented semantic facts into reusable
        procedural skills written to .draymond (fleet-visible), so the brain
        'learns how' — not just 'learns that'."""
        facts = self.semantic.all()
        candidates = [f for f in facts if float(f.get("confidence", 0)) >= min_confidence]
        candidates.sort(key=lambda f: -float(f.get("confidence", 0)))
        skills = []
        for f in candidates[:max_skills]:
            text = f.get("fact", "").strip()
            if not text:
                continue
            # Only facts that read as a reusable how-to/pattern.
            lowered = text.lower()
            if not any(k in lowered for k in ("when ", "if ", "use ", "set ", "run ", "check ", "ensure ",
                                              "fix ", "avoid ", "always ", "never ", "prefer ", "to ")):
                continue
            ok = self.ecosystem.append_lesson(
                pattern="derived-skill",
                lesson=f"[skill] {text[:400]}",
                agent_id="deterministic-brain",
            )
            if ok:
                skills.append(text[:200])
        return skills

    def _maybe_compress(self, thread: str, user: str, result: str, max_turns: int = 6) -> None:
        """Recursively compress a thread summary when it grows past max_turns."""
        svc = self._service()
        if not svc.is_available():
            return
        data = self.summaries._load()
        entry = data.get(thread, {})
        turns = int(entry.get("turns", 0)) + 1
        if turns % max_turns != 0:
            self.summaries.update(thread, entry.get("summary", ""), turns)
            return
        prev = entry.get("summary", "")
        prompt = (
            "Compress the running conversation summary, preserving all durable facts "
            "and decisions. Keep it under 400 words.\n\n"
            f"Previous summary:\n{prev}\n\n"
            f"New exchange:\nUSER: {user[:600]}\nASSISTANT: {result[:600]}"
        )
        compressed = svc.chat("You are a memory compression engine.", prompt, max_tokens=400)
        if compressed:
            self.summaries.update(thread, compressed, turns)

    def _memory_only_answer(self, user: str, thread: str) -> str:
        """Deterministic answer when the local backend is down — never a stall."""
        memories = self.recall(user, top_k=3)
        if memories:
            return "[memory-only] " + " | ".join(memories)
        return "[local model offline — deterministic mode]"

    # ---- status / fleet reporting ----

    def status(self) -> Dict[str, Any]:
        svc = self._service()
        base = svc.status() if svc else {"available": False}
        fast_model = None
        try:
            b = svc.active_backend()
            if b and hasattr(b, "fast_model_name"):
                fast_model = b.fast_model_name()
        except Exception:
            pass
        try:
            from brain.soul import get_soul
            identity = get_soul().identity
            soul_name = identity.get("name", "")
        except Exception:
            soul_name = ""
        return {
            **base,
            "fast_model": fast_model,
            "vision": self.supports_vision(),
            "harness": "local_model",
            "identity": soul_name or "unknown",
            "memory": {
                "episodes": self.episodic.count(),
                "semantic_facts": len(self.semantic.all()),
                "threads": len(self.summaries._load()),
            },
            "ecosystem": {
                "draymond_dir": str(self.ecosystem.dir),
                "lessons_readable": self.ecosystem.dir.exists(),
            },
        }


_harness: LocalModelHarness | None = None
_harness_lock = threading.Lock()


def get_harness() -> LocalModelHarness:
    global _harness
    if _harness is None:
        with _harness_lock:
            if _harness is None:
                _harness = LocalModelHarness()
    return _harness


def reset_harness() -> None:
    global _harness
    with _harness_lock:
        _harness = None


def consolidate_now(max_episodes: int = 12) -> Dict[str, Any]:
    """Module-level convenience for skill-chains / cron: distill episodes."""
    return get_harness().consolidate(max_episodes=max_episodes)


def briefing_now(focus: str = "fleet ops") -> str:
    """Module-level convenience for skill-chains / cron: local-model briefing."""
    return get_harness().briefing(focus=focus)


def evolve_now() -> Dict[str, Any]:
    """Module-level convenience for skill-chains / cron: self-evolving memory."""
    return get_harness().evolve_memory()

"""Smart Chat Router — intent classification + KB search + task routing.

Replaces the naive `/chat` that just hits `/task`. Now:
  GREETING → respond with capabilities
  QUESTION → search knowledge bank
  BUILD    → route to task engine
  HELP     → list skills and commands
  STATUS   → system health and stats
"""
from __future__ import annotations
import re
from typing import Dict, List, Optional


class ChatIntent:
    GREETING = "greeting"
    FAREWELL = "farewell"
    QUESTION = "question"
    BUILD = "build"
    HELP = "help"
    STATUS = "status"
    UNKNOWN = "unknown"


INTENT_PATTERNS = {
    ChatIntent.GREETING: [
        r'\b(hello|hi|hey|sup|yo|howdy|greetings|good morning|good evening)\b',
        r"\bwhat'?s up\b", r"\bhow are you\b",
    ],
    ChatIntent.FAREWELL: [
        r'\b(bye|goodbye|see you|later|cya|peace|good night)\b',
    ],
    ChatIntent.HELP: [
        r'\b(help|what can you do|commands|skills available|how do you work|capabilities)\b',
    ],
    ChatIntent.STATUS: [
        r'\b(status|health|stats|how many|whats loaded|uptime)\b',
    ],
    ChatIntent.QUESTION: [
        r'\b(how|what|why|when|where|who|which|explain|tell me|can you|do you|is it|are there)\b',
    ],
    ChatIntent.BUILD: [
        r'\b(build|create|make|generate|scaffold|design|code|write|implement|deploy)\s+(a |an |the |some )?\w+',
        r'\b(add|fix|update|change|modify|refactor|optimize|convert)\s+',
    ],
}


def classify_intent(text: str) -> tuple[str, float]:
    """Classify user text into a chat intent."""
    text_lower = text.lower().strip()

    # Short messages
    words = text_lower.split()
    if len(words) <= 2:
        for p in INTENT_PATTERNS[ChatIntent.GREETING]:
            if re.search(p, text_lower):
                return ChatIntent.GREETING, 0.95
        for p in INTENT_PATTERNS[ChatIntent.FAREWELL]:
            if re.search(p, text_lower):
                return ChatIntent.FAREWELL, 0.95
        for p in INTENT_PATTERNS[ChatIntent.STATUS]:
            if re.search(p, text_lower):
                return ChatIntent.STATUS, 0.9
        for p in INTENT_PATTERNS[ChatIntent.HELP]:
            if re.search(p, text_lower):
                return ChatIntent.HELP, 0.9
        if text_lower.endswith("?"):
            return ChatIntent.QUESTION, 0.7
        return ChatIntent.UNKNOWN, 0.3

    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        s = 0.0
        for p in patterns:
            if re.search(p, text_lower):
                s += 1.0
        if s > 0:
            scores[intent] = s

    if not scores:
        return ChatIntent.UNKNOWN, 0.3

    best = max(scores, key=scores.get)
    confidence = min(scores[best] / 3.0, 1.0)
    return best, confidence


def handle_chat(text: str) -> Dict:
    """Full chat pipeline: classify → route → respond."""
    intent, confidence = classify_intent(text)

    if intent == ChatIntent.GREETING:
        return _greeting()

    if intent == ChatIntent.FAREWELL:
        return {"intent": intent, "type": "text",
                "text": "Goodbye! Clear skies.", "actions": []}

    if intent == ChatIntent.STATUS:
        return _status()

    if intent == ChatIntent.HELP:
        return _help_response()

    if intent == ChatIntent.QUESTION:
        return _answer_question(text)

    if intent == ChatIntent.BUILD:
        return _route_to_build(text)

    return _fallback(text)


def _greeting() -> Dict:
    return {
        "intent": "greeting", "type": "greeting",
        "text": "Hello! I'm your deterministic brain. I can build websites, APIs, components, docs, and more. What would you like to make?",
        "actions": [
            {"label": "Build a website", "query": "build a landing page"},
            {"label": "Build an API", "query": "scaffold a REST API"},
            {"label": "Create a component", "query": "create a react component named UserCard"},
            {"label": "What can you do?", "query": "help"},
        ],
    }


def _help_response() -> Dict:
    try:
        from orchestration.skill_registry import get_skill_registry
        sr = get_skill_registry()
        sr.discover()
        skills = sr.list_all()
        by_backend = {}
        for s in skills:
            be = s.backend or "local"
            by_backend.setdefault(be, []).append(s.skill_name)
    except Exception:
        by_backend = {"local": ["react", "rest-api", "auth", "docker", "audit-repo"]}

    return {
        "intent": "help", "type": "help",
        "text": f"I have {sum(len(v) for v in by_backend.values())} skills across {len(by_backend)} backends.",
        "skills": {k: v[:10] for k, v in by_backend.items()},
        "actions": [
            {"label": "Build a website", "query": "build a landing page"},
            {"label": "Search knowledge", "query": "how to use React hooks"},
            {"label": "Show status", "query": "status"},
        ],
    }


def _status() -> Dict:
    import os
    try:
        from orchestration.skill_registry import get_skill_registry
        sr = get_skill_registry()
        sr.discover()
        skill_count = len(sr.list_all())
    except Exception:
        skill_count = "?"

    try:
        from knowledge.bank import get_knowledge_bank
        kb = get_knowledge_bank().stats()
        kb_count = kb.get("total_fragments", 0) + kb.get("snippets", 0)
    except Exception:
        kb_count = "?"

    try:
        from brain.soul import get_soul
        soul = get_soul()
        soul_name = soul.name or "(none)"
    except Exception:
        soul_name = "(none)"

    llm = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

    return {
        "intent": "status", "type": "status",
        "text": f"Skills: {skill_count} | Knowledge: {kb_count} | Soul: {soul_name} | LLM: {'ON' if llm else 'OFF'}",
        "stats": {"skills": skill_count, "knowledge": kb_count, "soul": soul_name, "llm": llm},
        "actions": [{"label": "List skills", "query": "help"}, {"label": "Start building", "query": "build a landing page"}],
    }


def _answer_question(text: str) -> Dict:
    kb_results = []
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        results = bank.query(text, top_k=3)
        for frag, score in results:
            if score > 0.1:
                kb_results.append({
                    "title": frag.source_title,
                    "text": frag.chunk_text[:300],
                    "source": frag.source_url,
                    "score": round(score, 3),
                })
    except Exception:
        pass

    if kb_results:
        best = kb_results[0]
        return {
            "intent": "question", "type": "kb_answer",
            "text": f"Found {len(kb_results)} relevant entries. Top match: **{best['title']}** — {best['text'][:200]}",
            "kb_results": kb_results,
            "actions": [
                {"label": "Build something", "query": "build a landing page"},
                {"label": "Add knowledge", "query": "help"},
            ],
        }

    return {
        "intent": "question", "type": "text",
        "text": "I don't have that in my knowledge bank yet. Try adding relevant docs via the Knowledge tab, or ask me to build something.",
        "actions": [
            {"label": "Add knowledge", "query": "help"},
            {"label": "Build a website", "query": "build a landing page"},
        ],
    }


def _route_to_build(text: str) -> Dict:
    try:
        from orchestration.dca_engine import DeterministicCodingAgent
        agent = DeterministicCodingAgent()
        result = agent.handle(text)
        fo = result.get("final_output", {})
        response = {
            "intent": "build", "type": "build_result",
            "status": result.get("status", "?"),
            "text": fo.get("output", "Build complete.")[:400],
            "preview_url": fo.get("preview_url"),
            "artifacts": fo.get("artifacts", []),
            "actions": [],
        }
        if response["preview_url"]:
            response["actions"].append({"label": "Open preview", "url": response["preview_url"]})
        response["actions"].append({"label": "Build something else", "query": "build a dashboard"})
        return response
    except Exception as e:
        return {"intent": "build", "type": "error", "text": f"Build failed: {str(e)}", "actions": []}


def _fallback(text: str) -> Dict:
    return {
        "intent": "unknown", "type": "text",
        "text": "Not sure what you mean. Try: 'build a landing page', 'how to use React hooks', or 'help'.",
        "actions": [
            {"label": "Build something", "query": "build a landing page"},
            {"label": "Help", "query": "help"},
            {"label": "Status", "query": "status"},
        ],
    }

"""Ollama Local LLM Client — Gemma for lightweight, zero-cost tasks.

Runs locally on your hardware. No API keys. No rate limits. Infinite.
Used for: simple chat, code scaffolding, tool call routing, small skill work.

The heavy research and analysis goes to external APIs (Gemini, OpenRouter).
This is your free, private, always-available co-pilot.

Default model: gemma3:4b (fits on low-spec laptops, ~3GB RAM)
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

try:
    import ollama
    _OLLAMA_OK = True
except ImportError:
    _OLLAMA_OK = False
    ollama = None  # type: ignore


class OllamaClient:
    """Local LLM via Ollama. Uses Gemma 4B for lightweight tasks.

    Models to try (in order of capability vs RAM):
      - gemma3:4b   (~3GB) — good reasoning, code
      - gemma3:1b   (~1GB) — ultra-light, fast
      - llama3.2:3b (~2GB) — strong all-around
      - qwen3:4b    (~3GB) — excellent code generation
    """

    def __init__(self, model: str = "gemma3:4b"):
        self.model = model
        self._available = _OLLAMA_OK

    def _check(self):
        if not _OLLAMA_OK:
            return False
        try:
            ollama.list()
            return True
        except Exception:
            return False

    def chat(self, prompt: str, system: str = "",
             temperature: float = 0.7) -> Dict:
        """Simple chat with Gemma. For questions, small coding tasks, quick help."""
        if not self._check():
            return {"ok": False, "error": "Ollama not running. Install: pip install ollama && ollama serve"}

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={"temperature": temperature, "num_predict": 1024},
            )
            return {
                "ok": True,
                "model": self.model,
                "text": response["message"]["content"],
                "done": response.get("done", True),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def scaffold(self, spec: str, language: str = "python") -> Dict:
        """Generate code scaffolding from a spec. Keep it light.

        Example: scaffold('REST API with 3 endpoints', 'python')
        """
        system = (
            f"You are a {language} code scaffold generator. Generate ONLY the "
            f"file structure and skeleton code with type hints and docstrings. "
            f"No explanations. No comments. Just code that compiles."
        )
        prompt = f"Scaffold this {language} project:\n{spec}"
        return self.chat(prompt, system=system, temperature=0.3)

    def route_task(self, query: str, available_skills: List[str]) -> Dict:
        """Route a user query to the best skill/tool. Deterministic backup.

        Returns JSON: {"skill": "skill_name", "confidence": 0.9, "reason": "..."}
        """
        skills_text = "\n".join(f"- {s}" for s in available_skills)
        system = (
            "You are a task router. Given a user query and available skills, "
            "return ONLY valid JSON with: skill (best match), confidence (0-1), "
            "reason (one sentence). No other output."
        )
        prompt = f"Query: {query}\n\nSkills:\n{skills_text}"

        result = self.chat(prompt, system=system, temperature=0.1)
        if result.get("ok") and result.get("text"):
            try:
                text = result["text"].strip()
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                return {"ok": True, "routing": json.loads(text)}
            except (json.JSONDecodeError, KeyError):
                pass
        return {"ok": False, "error": "Routing failed — use deterministic router"}

    def quick_code(self, task: str, language: str = "python") -> Dict:
        """Generate a small, self-contained code snippet."""
        system = (
            f"Generate ONLY the {language} code. No explanations. "
            f"No markdown fences. Just working code. Keep it under 50 lines."
        )
        return self.chat(task, system=system, temperature=0.3)

    def explain(self, code: str) -> Dict:
        """Explain what a piece of code does in plain English."""
        system = "Explain this code in 2-3 sentences at most. Be clear and concise."
        return self.chat(f"Explain:\n```\n{code[:3000]}\n```", system=system)

    def models(self) -> List[Dict]:
        """List available Ollama models."""
        if not self._check():
            return []
        try:
            models = ollama.list()
            return [{"name": m["name"], "size": m.get("size", 0)}
                    for m in models.get("models", [])]
        except Exception:
            return []

    def pull_model(self, model: str = "gemma3:4b") -> Dict:
        """Pull a model from Ollama."""
        if not _OLLAMA_OK:
            return {"ok": False, "error": "Ollama not installed"}
        try:
            ollama.pull(model)
            return {"ok": True, "model": model}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def status(self) -> Dict:
        available = self._check()
        models = self.models() if available else []
        return {
            "available": available,
            "model": self.model,
            "installed_models": [m["name"] for m in models],
            "ready": available and any(
                self.model.split(":")[0] in m["name"] for m in models
            ),
        }


def get_ollama(model: str = "gemma3:4b") -> OllamaClient:
    return OllamaClient(model=model)

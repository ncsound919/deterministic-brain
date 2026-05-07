"""Voice mode — bridges speech input through the dialogue pipeline to backend actions.

Architecture:
    STT (browser) → /voice/transcribe → VoiceMode.process() → route_intent() → backend
    Backend → VoiceMode → /voice/speak → TTS → browser plays audio

Intent routing maps:
    run_task    → agent.handle(query)
    run_bundle  → swarm.dispatch(bundle, inputs)
    relay       → relay.forward(agent, path, body)
    kairos_*    → kairos start/stop/status
    devpet_*    → DevPetTracker/Battle
    autodream   → run_autodream(dry_run)
    query_*     → dashboard queries
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from dialogue import create_dialogue_pipeline, DialoguePipeline, DialogueResult
from orchestration.event_bus import event_bus


class VoiceMode:
    """Wraps the DialoguePipeline and routes resolved intents to backend actions."""

    def __init__(self, seed: Optional[int] = None):
        self.pipeline: DialoguePipeline = create_dialogue_pipeline(seed)
        self._backends: Dict[str, callable] = {}
        self._session_id = f"voice_{int(time.time())}"

    def register_backend(self, intent_key: str, handler: callable) -> None:
        """Register a handler for a specific intent routing key."""
        self._backends[intent_key] = handler

    def process(self, text: str) -> Dict[str, Any]:
        """
        Run speech input through the full pipeline and route to backend.

        Returns a dict with:
            - response: str  (the final text to speak back)
            - result: any    (the backend action result)
            - dialogue: DialogResult  (the full pipeline output)
        """
        # Step 1: Dialogue pipeline
        dialogue_result: DialogueResult = self.pipeline.process(text)

        # Step 2: Route intent to backend
        backend_result = self._route_intent(dialogue_result)

        # Step 3: Build final response
        response_text = dialogue_result.response or ""
        if backend_result and isinstance(backend_result, dict):
            status = backend_result.get("status", "ok")
            if status == "ok":
                response_text += " Task completed successfully."
            elif status == "failed":
                response_text += f" Task failed: {backend_result.get('error', 'unknown error')}"
            elif status == "blocked":
                response_text += " Task was blocked by pre-audit checks."

        # Step 4: Emit event
        event_bus.emit("voice_turn",
            session_id=self._session_id,
            input_text=text,
            intent=dialogue_result.intent,
            response=response_text,
        )

        return {
            "response": response_text,
            "result": backend_result,
            "dialogue": {
                "intent": dialogue_result.intent,
                "confidence": dialogue_result.intent_confidence,
                "slots": dialogue_result.slots,
                "state": dialogue_result.state,
                "action": dialogue_result.action,
            },
        }

    def _route_intent(self, result: DialogueResult) -> Optional[Dict]:
        """Route the dialogue result intent to the appropriate backend handler."""
        intent = result.intent
        text = result.normalized_text or result.input_text
        slots = result.slots or {}

        # Delegate to registered backends
        handler = self._backends.get(intent)
        if handler:
            return handler(text=text, slots=slots, result=result)

        # Fallback intents
        if intent in ("command", "statement"):
            # Try to extract a task or bundle from slots
            action = slots.get("action", text)
            obj = slots.get("object", "")
            query = f"{action} {obj}".strip()

            handler = self._backends.get("run_task")
            if handler:
                return handler(text=query, slots=slots, result=result)

        return {"status": "unrouted", "intent": intent, "message": f"No handler for intent: {intent}"}

    def reset(self) -> None:
        self.pipeline.reset()
        self._session_id = f"voice_{int(time.time())}"

    def close(self) -> None:
        self.pipeline.close()


# ── Intent-to-backend router (used by server.py to configure VoiceMode) ──

def create_default_voice_mode() -> VoiceMode:
    """Create a VoiceMode with default backend handlers registered.

    The server is responsible for injecting actual backend instances
    via register_backend() after creation.
    """
    return VoiceMode(seed=42)

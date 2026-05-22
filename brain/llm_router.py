"""Multi-Model Cost Orchestrator with Local Fallback.

Optimizes LLM usage by routing tasks based on complexity with local model fallback:
1.  SIMPLE (summarization, formatting) -> local model OR gpt-4o-mini / gemini-flash
2.  COMPLEX (coding, architecture) -> claude-3-5-sonnet / gpt-4o WITH local fallback
3.  REASONING (planning, deep audit) -> o1-preview / claude-3-opus WITH local fallback
"""
import os
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

@dataclass
class LLMUsage:
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0

class CostOrchestrator:
    """Intelligent router for cost-effective LLM orchestration with local fallback."""
    
    MODELS = {
        "cheap": os.getenv("LLM_CHEAP", "gpt-4o-mini"),
        "smart": os.getenv("LLM_SMART", "claude-3-5-sonnet-20240620"),
        "heavy": os.getenv("LLM_HEAVY", "o1-preview"),
    }
    
    PRICING = {
        "gpt-4o-mini": {"in": 0.15, "out": 0.60}, # per 1M tokens
        "claude-3-5-sonnet-20240620": {"in": 3.00, "out": 15.00},
        "o1-preview": {"in": 15.00, "out": 60.00},
    }
    
    # Local model configuration
    LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8082")
    LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma-4-e2b.gguf")
    LOCAL_MODEL_ENABLED = os.getenv("LOCAL_MODEL_ENABLED", "true").lower() == "true"
    DETERMINISTIC_MODE = os.getenv("DETERMINISTIC_MODE", "true").lower() == "true"

    def __init__(self):
        self.stats: List[LLMUsage] = []
        self.total_cost = 0.0
        self.remote_failure_count = 0
        self.circuit_breaker_threshold = int(os.getenv("REMOTE_FAILURE_THRESHOLD", "3"))
        self.circuit_reset_seconds = int(os.getenv("FALLBACK_COOLDOWN_SECONDS", "300"))
        self.last_remote_failure = 0

    def _is_local_model_available(self) -> bool:
        """Check if the local model server is responding."""
        if not self.LOCAL_MODEL_ENABLED:
            return False
            
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{self.LOCAL_MODEL_URL}/v1/models")
                return resp.status_code == 200
        except Exception:
            return False

    def _is_deterministic_task(self, task_desc: str) -> bool:
        """Identify tasks suitable for local model (fast, free, deterministic)."""
        deterministic_keywords = [
            "format", "summarize", "extract", "list", "convert", 
            "parse", "validate", "template", "fill", "complete",
            "correct", "fix spelling", "grammar", "translate short",
            "calculate", "compute", "sort", "filter", "map"
        ]
        return any(kw in task_desc for kw in deterministic_keywords)

    def _should_use_local_fallback(self) -> bool:
        """Determine if we should use local model due to remote failures."""
        if self.remote_failure_count >= self.circuit_breaker_threshold:
            # Check if cooldown period has passed
            if time.time() - self.last_remote_failure < self.circuit_reset_seconds:
                return True
            else:
                # Reset after cooldown period
                self.remote_failure_count = 0
                self.last_remote_failure = 0
        return False

    def _record_remote_failure(self):
        """Record a remote API failure for circuit breaker."""
        self.remote_failure_count += 1
        self.last_remote_failure = time.time()

    def route(self, task_description: str) -> str:
        """Heuristically determine the best model for the task with local fallback."""
        t = task_description.lower()
        
        # Check if we should use local fallback due to remote failures
        if self._should_use_local_fallback() and self._is_local_model_available():
            logger.info("LLM Router: Using local model due to remote failure circuit breaker")
            return "local"
        
        # PRIORITY 1: Use local model for deterministic/simple tasks if available and enabled
        if (self.DETERMINISTIC_MODE and 
            self._is_local_model_available() and 
            self._is_deterministic_task(t)):
            logger.info("LLM Router: Using local model for deterministic task")
            return "local"
            
        # PRIORITY 2: Heavy reasoning
        if any(w in t for w in ["optimize", "architect", "deep audit", "refactor core"]):
            return self.MODELS["heavy"]
            
        # PRIORITY 3: Smart coding
        if any(w in t for w in ["build", "create", "implement", "fix bug", "react", "python"]):
            return self.MODELS["smart"]
            
        # PRIORITY 4: Cheap text processing
        return self.MODELS["cheap"]

    def log_usage(self, model: str, tokens_in: int, tokens_out: int):
        # Handle local model special case
        if model == "local":
            cost = 0.0  # Local model is free
        else:
            p = self.PRICING.get(model, {"in": 0, "out": 0})
            cost = (tokens_in * p["in"] + tokens_out * p["out"]) / 1_000_000
            
        usage = LLMUsage(model, tokens_in, tokens_out, cost)
        self.stats.append(usage)
        self.total_cost += cost
        logger.info(f"LLM Router: Task completed on {model}. Cost: ${cost:.4f}")

    def get_summary(self) -> Dict:
        return {
            "total_calls": len(self.stats),
            "total_cost": round(self.total_cost, 4),
            "by_model": {m: len([s for s in self.stats if s.model == m]) for m in set([s.model for s in self.stats])}
        }

_ROUTER: Optional[CostOrchestrator] = None

def get_llm_router() -> CostOrchestrator:
    global _ROUTER
    if _ROUTER is None: _ROUTER = CostOrchestrator()
    return _ROUTER

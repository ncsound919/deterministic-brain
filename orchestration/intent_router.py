from typing import Dict, Callable, Any
from loguru import logger
import re

class IntentRouter:
    """
    Improving User Interaction via Intent Routing.
    Uses a simple intent classifier (deterministic) to map queries to specific workflows.
    Avoids fixed pathways by allowing the central orchestrator to select the best tool.
    """
    def __init__(self):
        self.routes: Dict[str, Callable] = {}
        self.patterns: Dict[str, list[str]] = {}

    def register_intent(self, intent_name: str, keywords: list[str], handler: Callable):
        """Registers a workflow handler for a specific intent based on keywords/regex."""
        self.routes[intent_name] = handler
        self.patterns[intent_name] = keywords
        logger.info(f"Registered intent '{intent_name}' with keywords: {keywords}")

    def classify_intent(self, query: str) -> str:
        """Deterministic Intent Classifier"""
        query_lower = query.lower()
        for intent, keywords in self.patterns.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', query_lower):
                    return intent
        return "unknown"

    def route_query(self, query: str, context: Dict[str, Any] = None) -> Any:
        """
        Adaptive Tool Orchestration:
        Selects the best tool based on classified intent.
        """
        intent = self.classify_intent(query)
        logger.info(f"Query: '{query}' mapped to Intent: '{intent}'")
        
        if intent in self.routes:
            result = self.routes[intent](query, context)
            # Ensure every response carries intent/skill attribution
            if isinstance(result, dict):
                result["intent"] = intent
                result["skill"] = intent  # Backward compatible alias
            return result
        
        # Structured UI Feedback: Instead of guessing, ask for missing info
        return self.request_structured_feedback(query)

    def request_structured_feedback(self, query: str):
        """
        Structured UI Feedback: When confused, ask for specific fields 
        rather than trying to guess user intent.
        """
        logger.warning("Intent unknown. Requesting structured feedback from UI.")
        return {
            "status": "clarification_needed",
            "ui_action": "render_form",
            "message": "I couldn't confidently determine what you want to do. Please select a category:",
            "options": list(self.routes.keys()),
            "intent": "unknown",
            "skill": "unknown"
        }

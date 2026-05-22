"""Autonomous CEO — The strategic layer that runs the business.

Monitors portfolio, revenue, and sentiment to decide the next move.
"""
from __future__ import annotations
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from features.saas_builder import get_saas_builder
from tools.content_engine import get_content_engine
from tools.google_client import GoogleClient
from brain.soul import get_soul

logger = logging.getLogger(__name__)

class AutonomousCEO:
    """The brain's strategic layer for business operations."""
    
    def __init__(self, state_path: str = "data/ceo_state.json"):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.builder = get_saas_builder()
        self.content_engine = get_content_engine()
        self.google = GoogleClient()
        self.soul = get_soul()
        self._load_state()

    def _load_state(self):
        if self.state_path.exists():
            try:
                self.state = json.loads(self.state_path.read_text())
            except (json.JSONDecodeError, IOError, OSError):
                self.state = {"total_runs": 0, "last_decision": None}
        else:
            self.state = {"total_runs": 0, "last_decision": None}

    def _save_state(self):
        self.state["total_runs"] += 1
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def evaluate_portfolio(self) -> List[Dict]:
        """Check status of all SaaS projects and identify needs."""
        projects = self.builder.list_all()
        decisions = []
        
        for p in projects:
            # Simple heuristic-based decision making
            if p.stage == "research":
                decisions.append({
                    "project": p.name,
                    "action": "BUILD",
                    "reason": "Research completed, needs implementation."
                })
            elif p.stage == "deploy" and not p.price_usd:
                decisions.append({
                    "project": p.name,
                    "action": "MONETIZE",
                    "reason": "Deployed but no monetization set up."
                })
            elif p.stage == "monetize":
                decisions.append({
                    "project": p.name,
                    "action": "MARKET",
                    "reason": "Ready for traffic generation."
                })
                
        return decisions

    def sync_calendar_marketing(self) -> Dict:
        """Check calendar for events and generate marketing content."""
        cal = self.google.calendar_events(max_results=5)
        if not cal.get("ok"):
            logger.error(f"CEO: Calendar sync failed: {cal.get('error')}")
            return {"status": "error", "message": f"Could not read calendar: {cal.get('error')}"}
            
        events = cal.get("events", [])
        marketing_actions = []
        
        for event in events:
            summary = event.get("summary", "").lower()
            if any(word in summary for word in ["launch", "release", "ship", "update"]):
                topic = event.get("summary")
                platforms = ["twitter", "linkedin"]
                res = self.content_engine.schedule_content(topic, platforms)
                marketing_actions.append({
                    "event": topic,
                    "platforms": platforms,
                    "draft_id": res.get("draft_id")
                })
                
        return {"status": "ok", "actions": marketing_actions}

    def execute_strategy(self) -> Dict:
        """Main autonomous loop for the CEO."""
        logger.info("CEO: Executing strategic evaluation...")
        
        # 1. Evaluate Portfolio
        decisions = self.evaluate_portfolio()
        
        # 2. Sync Marketing with Reality
        marketing = self.sync_calendar_marketing()
        
        # 3. Consolidate into a Decision
        main_decision = {
            "timestamp": time.time(),
            "decisions": decisions,
            "marketing_sync": marketing,
            "mission_alignment": self.soul.agenda.get("mission") if hasattr(self.soul, 'agenda') else "unknown"
        }
        
        self.state["last_decision"] = main_decision
        self._save_state()
        
        return main_decision

# Singleton
_CEO: Optional[AutonomousCEO] = None

def get_ceo() -> AutonomousCEO:
    global _CEO
    if _CEO is None:
        _CEO = AutonomousCEO()
    return _CEO

"""Opportunity Scout — Autonomous trend detection and action planning.

Scans the news feed and knowledge bank to find 'opportunities' 
(market gaps, news-driven tasks, or synergy between projects).
"""
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class Opportunity:
    id: str
    title: str
    description: str
    source_news: str
    related_skill: Optional[str] = None
    action_plan: List[str] = field(default_factory=list)
    impact_score: float = 0.5 # 0.0 to 1.0
    ts_detected: float = field(default_factory=time.time)

class OpportunityScout:
    """Scouts for business opportunities using the brain's cross-domain knowledge."""
    
    def __init__(self):
        self.opportunities: List[Opportunity] = []

    def scout(self, news_items: List[Dict], soul_goals: List[str]) -> List[Opportunity]:
        """Analyze news against goals to find actionable opportunities."""
        found = []
        for item in news_items[:5]:
            title = item.get("title", "")
            # Simple heuristic for demo: if news matches goal keywords
            for goal in soul_goals:
                if any(word in title.lower() for word in goal.lower().split()):
                    opp = Opportunity(
                        id=f"opp-{int(time.time())}-{len(found)}",
                        title=f"Opportunity: {title[:40]}...",
                        description=f"Based on your goal '{goal}', this news item suggests a market pivot or new feature.",
                        source_news=title,
                        action_plan=[
                            f"Research {title[:20]} impact",
                            "Draft proposal in Media Studio",
                            "Schedule social post about this trend"
                        ],
                        impact_score=0.8
                    )
                    found.append(opp)
                    break
        
        self.opportunities = (found + self.opportunities)[:20]
        return found

    def get_latest(self) -> List[Dict]:
        return [o.__dict__ for o in self.opportunities]

_SCOUT: Optional[OpportunityScout] = None

def get_scout() -> OpportunityScout:
    global _SCOUT
    if _SCOUT is None: _SCOUT = OpportunityScout()
    return _SCOUT

def trigger_autonomous_scout():
    """Real-world actuator: Scout news and trigger trading bridge if alpha is found."""
    from features.finance_modules import get_news
    from brain.soul import get_soul
    from features.superalgos_bridge import get_superalgos_bridge
    
    scout = get_scout()
    news = get_news().fetch_all()
    soul = get_soul()
    
    opps = scout.scout(news, soul.goals)
    bridge = get_superalgos_bridge()
    
    for opp in opps:
        if opp.impact_score > 0.7:
            logger.info(f"High-impact opportunity found: {opp.title}. Triggering Superalgos Bridge...")
            bridge.send_signal(
                asset="BTC", 
                signal_type="BUY", 
                reason=opp.description,
                metadata={"opp_id": opp.id}
            )
    return len(opps)

"""Agent Registry — Defines the 'Flagship Agentic Systems' (Draymond, BlackMind, etc.)
as described in the AI Disruption Roadmap.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class FlagshipAgent:
    id: str
    name: str
    role: str
    status: str = "offline"
    capabilities: List[str] = field(default_factory=list)
    sector: str = "general"
    description: str = ""

class AgentRegistry:
    def __init__(self):
        self.agents = {
            "draymond": FlagshipAgent(
                id="draymond",
                name="Draymond",
                role="The Orchestrator",
                status="online",
                sector="orchestration",
                capabilities=["multi-agent coordination", "machine-speed routing", "performance analytics"],
                description="The point guard of the ecosystem. Conductor of all concurrent workflows."
            ),
            "blackmind": FlagshipAgent(
                id="blackmind",
                name="BlackMind",
                role="Scientific Brain",
                status="standby",
                sector="biotech",
                capabilities=["multi-omics", "CRISPR design", "reasoning-chains"],
                description="Deep transparent reasoning for high-stakes biotech and scientific research."
            ),
            "omni": FlagshipAgent(
                id="omni",
                name="OmniResearch Pro",
                role="Synthesis Engine",
                status="online",
                sector="intelligence",
                capabilities=["RAG", "literature discovery", "hypothesis generation"],
                description="Finds emerging value pools through pattern recognition across literature."
            ),
            "streetcode": FlagshipAgent(
                id="streetcode",
                name="StreetCode / TapIDE",
                role="AI-Native DevEnv",
                status="online",
                sector="development",
                capabilities=["vibe-coding", "local-context RAG", "infrastructure automation"],
                description="Local-first development environment with full context of your discography of code."
            )
        }

    def get_all(self) -> List[Dict]:
        from features.status_tracker import get_status_tracker
        tracker = get_status_tracker()
        out = []
        for agent_id, agent in self.agents.items():
            d = agent.__dict__.copy()
            d["status"] = tracker.get_agent_status(agent_id)
            out.append(d)
        return out

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        from features.status_tracker import get_status_tracker
        agent = self.agents.get(agent_id)
        if not agent:
            return None
        d = agent.__dict__.copy()
        d["status"] = get_status_tracker().get_agent_status(agent_id)
        return d

_REGISTRY = AgentRegistry()

def get_agent_registry():
    return _REGISTRY

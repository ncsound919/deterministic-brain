"""Content Engine for Deterministic Brain.

Uses local Gemma (Ollama) to generate and schedule content across platforms.
"""

from typing import Dict, List, Optional
import json
import uuid
from datetime import datetime
from pathlib import Path
from loguru import logger

from tools.local_gemma import get_gemma
from knowledge.bank import get_knowledge_bank

class ContentEngine:
    """Generates and manages multi-platform content schedules."""
    
    def __init__(self, drafts_dir: str = "data/content_drafts"):
        self.drafts_dir = Path(drafts_dir)
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.gemma = get_gemma()
        self.kb = get_knowledge_bank()
        
    def generate_post(self, topic: str, platform: str, context: Optional[str] = None) -> str:
        """Generate a social media post for a specific platform."""
        prompt = f"Write a highly engaging {platform} post about {topic}."
        if context:
            prompt += f"\nContext:\n{context}"
            
        if platform == "twitter":
            prompt += "\nKeep it under 280 characters and include 2-3 relevant hashtags."
        elif platform == "linkedin":
            prompt += "\nMake it professional but engaging, use bullet points if appropriate, and include hashtags."
        elif platform == "instagram":
            prompt += "\nFocus on visual descriptions and include many hashtags."
        elif platform == "email":
            prompt += "\nWrite a compelling subject line and a persuasive body."
        return self.gemma.complete(prompt, n_predict=300, temperature=0.7)

    def generate_campaign(self, topic: str, platforms: List[str]) -> Dict[str, str]:
        """Generate a full campaign across multiple platforms."""
        # Retrieve recent knowledge on the topic
        results = self.kb.query(topic, top_k=3)
        context = "\n".join([f"- {r[0].chunk_text}" for r in results]) if results else ""
        
        logger.info(f"Generating campaign for '{topic}' across {platforms}")
        campaign = {}
        for platform in platforms:
            campaign[platform] = self.generate_post(topic, platform, context)
            
        return campaign

    def save_draft(self, topic: str, content_dict: Dict[str, str]) -> str:
        """Save generated content as a draft."""
        draft_id = str(uuid.uuid4())[:8]
        draft = {
            "id": draft_id,
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "content": content_dict,
            "status": "draft"
        }
        
        draft_path = self.drafts_dir / f"{draft_id}.json"
        with open(draft_path, "w") as f:
            json.dump(draft, f, indent=2)
            
        logger.info(f"Saved content draft: {draft_id}")
        return draft_id
        
    def list_drafts(self) -> List[Dict]:
        """List all current drafts."""
        drafts = []
        for file_path in self.drafts_dir.glob("*.json"):
            try:
                with open(file_path, "r") as f:
                    drafts.append(json.load(f))
            except Exception:
                pass
        return sorted(drafts, key=lambda x: x.get("timestamp", ""), reverse=True)
        
    def schedule_content(self, topic: str, platforms: List[str], days: int = 1) -> Dict:
        """Entry point for the content-schedule skill."""
        campaign = self.generate_campaign(topic, platforms)
        draft_id = self.save_draft(topic, campaign)
        
        return {
            "ok": True,
            "draft_id": draft_id,
            "topic": topic,
            "platforms": platforms,
            "content": campaign,
            "message": f"Generated and scheduled {len(platforms)} posts for '{topic}'."
        }

# Global instance
_engine = None

def get_content_engine() -> ContentEngine:
    global _engine
    if _engine is None:
        _engine = ContentEngine()
    return _engine

"""Content Engine for Deterministic Brain.

Uses the unified local model (Ollama / llama-server / llama.cpp) to generate
and schedule content across platforms. Falls back gracefully when no local
backend is running.

CRM wiring (:mod:`tools.crm`) supplies the audience a campaign aims at:
``generate_campaign``/``schedule_content`` take a ``segment`` selector (a tag
or a company in the CRM contact store) and resolve it to real contacts before
any copy is written, so a draft records which audience it was aimed at rather
than asserting one. With an empty CRM the engine degrades to the previous
behaviour and stamps no provenance — it never invents an audience.
"""

from typing import Dict, List, Optional, Union
import json
import uuid
from datetime import datetime
from pathlib import Path
from loguru import logger

from tools.local_model import get_local_model
from knowledge.bank import get_knowledge_bank

_BRAIN_ROOT = Path(__file__).resolve().parents[1]

#: What ``segment`` may be: a bare tag/company string, or an explicit selector.
SegmentSelector = Union[str, Dict[str, str], None]


class ContentEngine:
    """Generates and manages multi-platform content schedules."""

    def __init__(self, drafts_dir: str = "data/content_drafts"):
        self.drafts_dir = Path(drafts_dir)
        if not self.drafts_dir.is_absolute():
            self.drafts_dir = _BRAIN_ROOT / self.drafts_dir
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        self.llm = get_local_model()
        self.kb = get_knowledge_bank()

    # ------------------------------------------------------------------
    # CRM audience resolution
    # ------------------------------------------------------------------
    def _resolve_segment(self, segment: SegmentSelector) -> Optional[Dict]:
        """Resolve a ``segment`` selector against the CRM contact store.

        Returns ``None`` when the selector is empty or resolves to nothing —
        the caller must then produce audience-free content rather than guess.
        """
        if not segment:
            return None
        try:
            from tools.crm import get_crm_store

            store = get_crm_store()
        except Exception as e:  # noqa: BLE001 — a broken store must not block content
            logger.debug("CRM store unavailable for segment resolution: %s", e)
            return None

        if isinstance(segment, str):
            for selector in ({"tags": segment}, {"company": segment}):
                hits = store.search_contacts(**selector)
                if hits:
                    return self._segment_summary(segment, "tag" if "tags" in selector else "company", hits)
            return None

        if isinstance(segment, dict):
            selector = {k: v for k, v in segment.items() if v}
            if not selector:
                return None
            hits = store.search_contacts(**selector)
            if not hits:
                return None
            label = selector.get("tags") or selector.get("company") or selector.get("status") or "segment"
            field = "tags" if "tags" in selector else ("company" if "company" in selector else "status")
            return self._segment_summary(label, field, hits)

        logger.warning("Unsupported segment selector of type %s — ignoring", type(segment).__name__)
        return None

    @staticmethod
    def _segment_summary(label: str, field: str, hits: List[Dict]) -> Dict:
        deals = []
        try:
            from tools.crm import get_crm_store

            store = get_crm_store()
            ids = {c.get("id") for c in hits}
            deals = [d for d in store.open_deals() if d.get("contact_id") in ids]
        except Exception as e:  # noqa: BLE001
            logger.debug("Open-deal lookup for segment failed: %s", e)
        return {
            "segment": label,
            "field": field,
            "contact_count": len(hits),
            "contact_ids": [c.get("id") for c in hits],
            "companies": sorted({c.get("company") for c in hits if c.get("company")}),
            "open_deal_count": len(deals),
            "open_value": round(sum(float(d.get("value") or 0.0) for d in deals), 2),
        }

    @staticmethod
    def _audience_prompt(audience: Dict) -> str:
        """The audience clause appended to a generation prompt."""
        parts = [
            f"Audience: {audience['contact_count']} CRM contact(s)"
            f" in the '{audience['segment']}' {audience['field']} segment."
        ]
        if audience.get("companies"):
            parts.append("Companies: " + ", ".join(audience["companies"][:5]) + ".")
        if audience.get("open_deal_count"):
            parts.append(
                f"{audience['open_deal_count']} open deal(s) worth "
                f"${audience['open_value']:,.2f} depend on this segment — write toward closing them."
            )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # generation
    # ------------------------------------------------------------------
    def generate_post(self, topic: str, platform: str, context: Optional[str] = None,
                      audience: Optional[Dict] = None) -> str:
        """Generate a social media post for a specific platform."""
        prompt = f"Write a highly engaging {platform} post about {topic}."
        if context:
            prompt += f"\nContext:\n{context}"
        if audience:
            prompt += f"\n{self._audience_prompt(audience)}"

        if platform == "twitter":
            prompt += "\nKeep it under 280 characters and include 2-3 relevant hashtags."
        elif platform == "linkedin":
            prompt += "\nMake it professional but engaging, use bullet points if appropriate, and include hashtags."
        elif platform == "instagram":
            prompt += "\nFocus on visual descriptions and include many hashtags."
        elif platform == "email":
            prompt += "\nWrite a compelling subject line and a persuasive body."
        return self.llm.complete(prompt, max_tokens=300, temperature=0.7)

    def generate_campaign(self, topic: str, platforms: List[str],
                          segment: SegmentSelector = None) -> Dict[str, str]:
        """Generate a full campaign across multiple platforms.

        ``segment`` (a CRM tag/company, or a selector dict) aims the campaign at
        a real audience. Knowledge-bank retrieval and the audience are both
        prepended to every platform prompt.
        """
        # Retrieve recent knowledge on the topic
        results = self.kb.query(topic, top_k=3)
        context = "\n".join([f"- {r[0].chunk_text}" for r in results]) if results else ""

        audience = self._resolve_segment(segment)
        logger.info(
            "Generating campaign for '%s' across %s%s",
            topic,
            platforms,
            f" aimed at CRM segment '{audience['segment']}' ({audience['contact_count']} contacts)"
            if audience else " (no CRM segment)",
        )
        campaign = {}
        for platform in platforms:
            campaign[platform] = self.generate_post(topic, platform, context, audience)

        return campaign

    def save_draft(self, topic: str, content_dict: Dict[str, str],
                   crm: Optional[Dict] = None) -> str:
        """Save generated content as a draft.

        ``crm`` carries the resolved audience provenance. It is written only
        when supplied, so an empty CRM produces a draft that says nothing
        about audience rather than claiming one.
        """
        draft_id = str(uuid.uuid4())[:8]
        draft = {
            "id": draft_id,
            "topic": topic,
            "timestamp": datetime.now().isoformat(),
            "content": content_dict,
            "status": "draft"
        }
        if crm:
            draft["crm"] = crm

        draft_path = self.drafts_dir / f"{draft_id}.json"
        with open(draft_path, "w") as f:
            json.dump(draft, f, indent=2)

        logger.info("Saved content draft: %s", draft_id)
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

    def schedule_content(self, topic: str, platforms: List[str], days: int = 1,
                         segment: SegmentSelector = None) -> Dict:
        """Entry point for the content-schedule skill."""
        audience = self._resolve_segment(segment)
        campaign = self.generate_campaign(topic, platforms, segment=segment)
        draft_id = self.save_draft(topic, campaign, crm=audience)

        return {
            "ok": True,
            "draft_id": draft_id,
            "topic": topic,
            "platforms": platforms,
            "content": campaign,
            "crm": audience,
            "message": f"Generated and scheduled {len(platforms)} posts for '{topic}'."
        }

# Global instance
_engine = None

def get_content_engine() -> ContentEngine:
    global _engine
    if _engine is None:
        _engine = ContentEngine()
    return _engine

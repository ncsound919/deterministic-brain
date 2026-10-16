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

    def _log_marketing_touch(self, subject_type: str, subject_id: str, note: str,
                             draft_id: Optional[str] = None) -> Optional[Dict]:
        """Record a marketing touch against a CRM contact or deal.

        Best-effort by design: the CRM is a record of what marketing did, not a
        gate on it. A store failure is logged and returns ``None`` — the
        campaign still happened.
        """
        try:
            from tools.crm import get_crm_store

            store = get_crm_store()
        except Exception as e:  # noqa: BLE001
            logger.warning("CEO: CRM store unavailable for marketing write-back: %s", e)
            return None
        try:
            return store.log_activity(
                subject_type, subject_id, kind="marketing", note=note
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("CEO: CRM marketing write-back failed (%s/%s): %s", subject_type, subject_id, e)
            return None

    def _crm(self):
        """The CRM store, or ``None`` when it cannot be opened."""
        try:
            from tools.crm import get_crm_store

            return get_crm_store()
        except Exception as e:  # noqa: BLE001
            logger.warning("CEO: CRM unavailable: %s", e)
            return None

    def sync_calendar_marketing(self) -> Dict:
        """Check calendar for events and generate marketing content.

        Calendar events are matched against open CRM deals; a hit writes a
        marketing activity back to that deal so the pipeline records the touch.
        """
        cal = self.google.calendar_events(max_results=5)
        if not cal.get("ok"):
            logger.error(f"CEO: Calendar sync failed: {cal.get('error')}")
            return {"status": "error", "message": f"Could not read calendar: {cal.get('error')}"}

        store = self._crm()
        events = cal.get("events", [])
        marketing_actions = []

        for event in events:
            summary = event.get("summary", "").lower()
            if any(word in summary for word in ["launch", "release", "ship", "update"]):
                topic = event.get("summary")
                platforms = ["twitter", "linkedin"]
                # Match the event against open CRM deals once, then use the
                # match for both the audience and the write-back.
                matched = self._deals_matching_summary(store, summary) if store else []
                res = self.content_engine.schedule_content(
                    topic, platforms,
                    segment=matched[0].get("contact_email") if matched else None,
                )
                action = {
                    "event": topic,
                    "platforms": platforms,
                    "draft_id": res.get("draft_id"),
                    "crm": res.get("crm"),
                }
                action["crm_activities"] = [
                    a["id"]
                    for deal in matched
                    if (a := self._log_marketing_touch(
                        "deal", str(deal.get("id")),
                        f"calendar-driven campaign for '{topic}'",
                    ))
                ]
                marketing_actions.append(action)

        return {"status": "ok", "actions": marketing_actions}

    @staticmethod
    def _deals_matching_summary(store, summary: str) -> List[Dict]:
        """Open deals whose title shares a word with the calendar event.

        Deliberately conservative: a 4+ character word must actually appear in
        both, so "release" does not match every deal that mentions "release".
        """
        words = {w for w in summary.split() if len(w) > 3}
        if not words:
            return []
        return [
            d for d in store.open_deals()
            if ({w for w in str(d.get("title", "")).lower().split() if len(w) > 3} & words)
        ]

    def sync_crm_marketing(self, limit: int = 3) -> Dict:
        """Generate marketing for the highest-value open CRM deals.

        This is the CRM-to-marketing direction: the pipeline decides what gets
        promoted, the contact segment decides who it is aimed at, and every
        generated draft writes an activity back to its deal.

        With an empty pipeline this returns zero actions rather than inventing
        a campaign.
        """
        store = self._crm()
        if store is None:
            return {"status": "error", "message": "CRM store unavailable"}

        deals = sorted(
            store.open_deals(),
            key=lambda d: -float(d.get("value") or 0.0),
        )[:limit]

        actions = []
        for deal in deals:
            contact_email = deal.get("contact_email")
            if not contact_email:
                continue
            res = self.content_engine.schedule_content(
                str(deal.get("title")),
                ["twitter", "linkedin", "email"],
                segment=contact_email,
            )
            activity_ids = []
            activity = self._log_marketing_touch(
                "deal", str(deal.get("id")),
                f"pipeline-driven campaign for '{deal.get('title')}'",
            )
            if activity:
                activity_ids.append(activity["id"])
            contact = store.find_contact(email=contact_email)
            if contact and contact.get("id"):
                contact_activity = self._log_marketing_touch(
                    "contact", str(contact["id"]),
                    f"marketing for deal '{deal.get('title')}'",
                )
                if contact_activity:
                    activity_ids.append(contact_activity["id"])
            actions.append({
                "deal_id": deal.get("id"),
                "deal": deal.get("title"),
                "value": deal.get("value"),
                "stage": deal.get("stage"),
                "contact": contact_email,
                "draft_id": res.get("draft_id"),
                "crm": res.get("crm"),
                "crm_activities": activity_ids,
            })

        return {"status": "ok", "actions": actions}

    def execute_strategy(self) -> Dict:
        """Main autonomous loop for the CEO."""

        # 1. Evaluate Portfolio
        decisions = self.evaluate_portfolio()

        # 2. Sync Marketing with Reality
        marketing = self.sync_calendar_marketing()

        # 3. Sync Marketing with the Pipeline
        crm_marketing = self.sync_crm_marketing()

        # 4. Consolidate into a Decision
        main_decision = {
            "timestamp": time.time(),
            "decisions": decisions,
            "marketing_sync": marketing,
            "crm_marketing_sync": crm_marketing,
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

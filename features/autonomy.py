"""Autonomy & Dream Engine — 24/7 background operations.

KAIROS cron tasks + AutoDream consolidation + skill expansion.
Wire this into the daemon for continuous autonomous operation.
"""
from __future__ import annotations
import os, json, time, logging, hashlib
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# DREAM CYCLE (enhanced AutoDream)
# ═══════════════════════════════════════════════════════════════

@dataclass
class DreamResult:
    cycle: int
    timestamp: str
    kb_consolidated: int            # fragments merged
    kb_pruned: int                  # stale fragments removed
    kb_refs_generated: int          # reference docs created
    skills_expanded: int            # new skills downloaded
    tasks_completed: int            # auto tasks executed
    soul_goals_processed: int       # soul goals turned into tasks
    suggestions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self): return self.__dict__


class DreamCycle:
    """Runs a complete dream cycle: consolidate KB, expand skills, process goals, generate suggestions."""

    def __init__(self, dream_log_path: str = ".dream_log.json"):
        self.log_path = dream_log_path
        self.cycles: List[DreamResult] = []
        self._load()

    def _load(self):
        if os.path.exists(self.log_path):
            try:
                data = json.loads(open(self.log_path).read())
                self.cycles = [DreamResult(**d) for d in data]
            except: pass

    def _save(self):
        with open(self.log_path, "w") as f:
            json.dump([c.to_dict() for c in self.cycles[-20:]], f, indent=2)

    def run(self, dry_run: bool = False) -> DreamResult:
        """Execute one full dream cycle."""
        errors = []
        suggestions = []
        kb_consolidated = 0; kb_pruned = 0; kb_refs = 0
        skills_expanded = 0; tasks_completed = 0; soul_goals = 0

        # 1. KB consolidation
        try:
            from brain.autodream import consolidate_knowledge_bank
            result = consolidate_knowledge_bank(dry_run=dry_run)
            if result.get("status") == "ok":
                kb_consolidated = result.get("fragments_merged", 0)
                kb_pruned = result.get("fragments_pruned", 0)
                kb_refs = result.get("refs_generated", 0)
        except Exception as e:
            errors.append(f"KB consolidation: {e}")

        # 2. Skill expansion
        try:
            from features.skill_expander import get_expander
            expander = get_expander()
            result = expander.expand(max_downloads=3)
            skills_expanded = result.get("downloaded", 0)
            if skills_expanded > 0:
                expander.refresh_registry()
                suggestions.append(f"Added {skills_expanded} new skill packs. Registry refreshed.")
        except Exception as e:
            errors.append(f"Skill expansion: {e}")

        # 3. Process soul goals into tasks
        try:
            from brain.soul import get_soul
            from features.planner import get_planner
            soul = get_soul()
            planner = get_planner()
            if soul.goals:
                new_tasks = planner.generate_from_soul(soul.goals)
                soul_goals = len(new_tasks)
                if soul_goals > 0:
                    suggestions.append(f"Generated {soul_goals} tasks from soul goals")
        except Exception as e:
            errors.append(f"Soul goals: {e}")

        # 4. Execute due tasks
        try:
            from features.planner import get_planner
            planner = get_planner()
            due = planner.get_due()
            for t in due[:3]:
                try:
                    planner.mark_running(t.id)
                    from orchestration.dca_engine import DeterministicCodingAgent
                    agent = DeterministicCodingAgent()
                    agent.handle(t.query)
                    planner.mark_done(t.id)
                    tasks_completed += 1
                except Exception as e:
                    planner.mark_failed(t.id, str(e))
        except Exception as e:
            errors.append(f"Task execution: {e}")

        # 5. Generate improvement suggestions
        suggestions.extend(self._generate_suggestions())

        result = DreamResult(
            cycle=len(self.cycles) + 1,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            kb_consolidated=kb_consolidated,
            kb_pruned=kb_pruned,
            kb_refs_generated=kb_refs,
            skills_expanded=skills_expanded,
            tasks_completed=tasks_completed,
            soul_goals_processed=soul_goals,
            suggestions=suggestions,
            errors=errors,
        )
        if not dry_run:
            self.cycles.append(result)
            self._save()
        return result

    def _generate_suggestions(self) -> List[str]:
        suggestions = []
        try:
            from knowledge.bank import get_knowledge_bank
            bank = get_knowledge_bank()
            stats = bank.stats()
            if stats.get("total_fragments", 0) < 10:
                suggestions.append("Knowledge bank is sparse — add URLs or docs via Settings")
            if stats.get("snippets", 0) < 3:
                suggestions.append("Save useful code snippets in the Knowledge tab")
        except: pass

        try:
            from orchestration.skill_registry import get_skill_registry
            sr = get_skill_registry()
            sr.discover()
            total = len(sr.list_all())
            if total < 120:
                suggestions.append(f"Only {total} skills loaded — run Skill Expansion")
        except: pass

        try:
            from brain.soul import get_soul
            soul = get_soul()
            if not soul.name:
                suggestions.append("Set up your identity in Settings to personalize the brain")
            if not soul.goals:
                suggestions.append("Add goals to your soul file so the brain can work toward them")
        except: pass

        try:
            plan_path = "planner_tasks.json"
            if os.path.exists(plan_path):
                tasks = json.loads(open(plan_path).read())
                pending = len([t for t in tasks if t.get("status") == "pending"])
                if pending < 2:
                    suggestions.append(f"Only {pending} pending tasks — add more scheduled builds")
            else:
                suggestions.append("No tasks scheduled — add recurring tasks in the Planner")
        except: pass

        return suggestions

    def get_stats(self) -> Dict:
        if not self.cycles:
            return {"cycles": 0, "last_cycle": None}
        last = self.cycles[-1]
        return {
            "cycles": len(self.cycles),
            "last_cycle": last.to_dict(),
            "total_skills_expanded": sum(c.skills_expanded for c in self.cycles),
            "total_tasks_completed": sum(c.tasks_completed for c in self.cycles),
            "total_kb_consolidated": sum(c.kb_consolidated for c in self.cycles),
        }


# ═══════════════════════════════════════════════════════════════
# AUTONOMY SCHEDULER
# ═══════════════════════════════════════════════════════════════

class AutonomyScheduler:
    """Schedules and runs autonomous operations on a timer."""

    def __init__(self):
        self.dream_cycle = DreamCycle()
        self.last_dream = 0
        self.last_expand = 0
        self.last_news = 0

    def tick(self) -> Dict:
        """Called every ~minute by KAIROS. Runs operations that are due."""
        now = time.time()
        actions = []

        # Dream cycle every 6 hours
        if now - self.last_dream > 21600:
            try:
                result = self.dream_cycle.run(dry_run=False)
                self.last_dream = now
                actions.append({
                    "action": "dream_cycle",
                    "kb_consolidated": result.kb_consolidated,
                    "skills_expanded": result.skills_expanded,
                    "suggestions": result.suggestions[:3],
                })
            except Exception as e:
                actions.append({"action": "dream_cycle", "error": str(e)})

        # Skill expansion every 3 hours
        if now - self.last_expand > 10800:
            try:
                from features.skill_expander import get_expander
                r = get_expander().expand(max_downloads=2)
                self.last_expand = now
                if r.get("downloaded", 0) > 0:
                    get_expander().refresh_registry()
                    actions.append({"action": "skill_expand", "downloaded": r["downloaded"]})
            except Exception as e:
                actions.append({"action": "skill_expand", "error": str(e)})

        # News fetch every 30 minutes
        if now - self.last_news > 1800:
            try:
                from features.finance_modules import get_news
                items = get_news().fetch_all()
                self.last_news = now
                if items:
                    actions.append({"action": "news_fetch", "items": len(items)})
            except: pass

        return {"tick": time.strftime("%H:%M:%S"), "actions": actions}

    def force_dream(self) -> Dict:
        result = self.dream_cycle.run(dry_run=False)
        self.last_dream = time.time()
        return result.to_dict()

    def get_status(self) -> Dict:
        return {
            "last_dream": time.strftime("%H:%M:%S", time.localtime(self.last_dream)) if self.last_dream else "never",
            "last_expand": time.strftime("%H:%M:%S", time.localtime(self.last_expand)) if self.last_expand else "never",
            "dream_stats": self.dream_cycle.get_stats(),
        }


# Singleton
_AUTONOMY: Optional[AutonomyScheduler] = None
def get_autonomy() -> AutonomyScheduler:
    global _AUTONOMY
    if _AUTONOMY is None: _AUTONOMY = AutonomyScheduler()
    return _AUTONOMY

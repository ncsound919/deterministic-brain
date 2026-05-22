"""Autonomy & Dream Engine — 24/7 background operations.

KAIROS cron tasks + AutoDream consolidation + skill expansion.
Wire this into the daemon for continuous autonomous operation.
"""
from __future__ import annotations
import os
import json
import time
import logging
from typing import Dict, List, Optional
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
                with open(self.log_path) as f:
                    data = json.loads(f.read())
                self.cycles = [DreamResult(**d) for d in data]
            except Exception:
                pass

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

        # 4. Self-Healing Benchmarker
        try:
            from self_healing import create_healer as create_self_healer
            from evolution.skill_evolver import SkillEvolver
            evolver = SkillEvolver()
            healer = create_self_healer("dream_cycle")
            
            # Check for skills with poor performance
            poor_skills = [s for s in evolver.all_stats() if s.get("score", 1.0) < 0.4]
            for s in poor_skills[:2]: # Only heal 2 at a time to save compute
                name = s.get("name")
                logger.info(f"Dream Cycle: Attempting self-healing for {name}...")
                heal_res = healer.attempt_auto_repair(name)
                if heal_res.get("status") == "repaired":
                    suggestions.append(f"Successfully self-healed broken skill: {name}")
                else:
                    suggestions.append(f"Skill {name} is degrading. Consider manual audit.")
        except Exception as e:
            errors.append(f"Self-healing: {e}")

        # 5. Execute due tasks
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
        except Exception: pass

        try:
            from orchestration.skill_registry import get_skill_registry
            sr = get_skill_registry()
            sr.discover()
            total = len(sr.list_all())
            if total < 120:
                suggestions.append(f"Only {total} skills loaded — run Skill Expansion")
        except Exception: pass

        try:
            from brain.soul import get_soul
            soul = get_soul()
            if not soul.name:
                suggestions.append("Set up your identity in Settings to personalize the brain")
            if not soul.goals:
                suggestions.append("Add goals to your soul file so the brain can work toward them")
        except Exception: pass

        try:
            plan_path = "planner_tasks.json"
            if os.path.exists(plan_path):
                with open(plan_path) as f:
                    tasks = json.loads(f.read())
                pending = len([t for t in tasks if t.get("status") == "pending"])
                if pending < 2:
                    suggestions.append(f"Only {pending} pending tasks — add more scheduled builds")
            else:
                suggestions.append("No tasks scheduled — add recurring tasks in the Planner")
        except Exception: pass

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
        # Initialize last-run times to NOW to prevent immediate execution storm on restart
        now = time.time()
        self.last_dream = now
        self.last_expand = now
        self.last_news = now
        self.last_social = now

    def tick(self) -> Dict:
        """Called every ~minute by KAIROS. Runs operations that are due."""
        now = time.time()
        actions = []

        # 1. Social Post execution (every minute)
        if now - self.last_social > 60:
            try:
                from features.social_scheduler import get_social
                from features.social_posting import SocialPoster
                ss = get_social()
                due = ss.get_due()
                if due:
                    sp = SocialPoster(headless=True)
                    try:
                        for post in due:
                            res = sp.post(post.platform, post.content, tags=post.tags)
                            if res.get("ok"):
                                ss.mark_posted(post.id, res)
                            else:
                                ss.mark_failed(post.id, res.get("error", "Unknown error"))
                        actions.append({"action": "social_posting", "count": len(due)})
                    finally:
                        sp.close()
                self.last_social = now
            except Exception as e:
                actions.append({"action": "social_posting", "error": str(e)})

        # 2. Dream cycle every 6 hours
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

        # News fetch & Opportunity Scout every 15 minutes (WEAPONIZED)
        if now - self.last_news > 900:
            try:
                from features.opportunity_scout import trigger_autonomous_scout
                opp_count = trigger_autonomous_scout()
                self.last_news = now
                if opp_count > 0:
                    actions.append({"action": "opportunity_scout", "found": opp_count, "triggered_actuators": True})
            except Exception as e:
                actions.append({"action": "opportunity_scout", "error": str(e)})

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

"""DeterministicCodingAgent — no-LLM core loop wired to ReasoningEngine."""
from __future__ import annotations
import glob
import math
import os
import re

_RE_STEP_SPLIT = re.compile(r"## Step \d+")
_RE_RENDER_TMPL = re.compile(r"Render template `(.+?)` with context")
_RE_WRITE_RESULT = re.compile(r"Write result to `(.+?)`")
_RE_RUN_LINTER = re.compile(r"Run linter on `(.+?)`")
_RE_RUN_COMMAND = re.compile(r"Run command `(.+?)`")
import yaml
import logging
from typing import Dict, List, Optional

from brain.task_parser import TaskParser
from brain.router import MoERouter
from brain.memory import init_state
from planners.monte_carlo import MonteCarloScaffolder
from reasoning.auditor import DeterministicAuditor
from reasoning.math_engine import ReasoningEngine, Constraint
from tools.registry import ToolRegistry
from tools.tracing import log_event

from orchestration import get_skill_registry, get_skill_executor
from reasoning.priority_engine import PriorityEngine
from orchestration.resource_allocator import ResourceAllocator

logger = logging.getLogger(__name__)


class SkillExecutor:
    def __init__(self, tool_registry: ToolRegistry):
        self.tools = tool_registry

    def execute(self, skill_path: str, inputs: Dict, context: Optional[Dict] = None) -> Dict:
        with open(skill_path, encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---"):
            raise ValueError(f"Invalid skill.md — {skill_path}")
        _, fm, md_body = content.split("---", 2)
        meta = yaml.safe_load(fm)
        for t in meta.get("tools", []):
            if not self.tools.has(t):
                raise ValueError(f"Tool '{t}' not in registry")
        ctx = {**inputs}
        # Merge in optional runtime context
        if context:
            ctx.update(context)
        for step in self._parse_steps(md_body):
            self._execute_step(step, ctx)
            log_event("step", {
                "skill": skill_path,
                "actions": [a for a, _ in step],
                "session_id": ctx.get("session_id"),
            })
        auditor  = DeterministicAuditor()
        audit_ok = auditor.run_audit(meta.get("audit", []), ctx)
        return {"success": audit_ok, "output": ctx.get("output_file", ""), "ctx": ctx}

    def _parse_steps(self, md_body: str):
        steps = []
        for block in _RE_STEP_SPLIT.split(md_body)[1:]:
            actions = []
            for line in block.strip().splitlines():
                line = line.strip()
                m = _RE_RENDER_TMPL.match(line)
                if m:
                    actions.append(("render_template", {"template": m.group(1)})); continue
                m = _RE_WRITE_RESULT.match(line)
                if m:
                    actions.append(("file_write", {"path": m.group(1)})); continue
                m = _RE_RUN_LINTER.match(line)
                if m:
                    actions.append(("run_linter", {"file": m.group(1)})); continue
                m = _RE_RUN_COMMAND.match(line)
                if m:
                    actions.append(("run_command", {"cmd": m.group(1)}))
            if actions:
                steps.append(actions)
        return steps

    def _execute_step(self, actions, ctx: Dict):
        for action, params in actions:
            if action == "render_template":
                from jinja2 import Environment, FileSystemLoader
                env  = Environment(loader=FileSystemLoader("."))
                tmpl = env.get_template(params["template"])
                ctx["_rendered"] = tmpl.render(**ctx)
            elif action == "file_write":
                path = params["path"]
                for k, v in ctx.items():
                    path = path.replace(f"{{{{{k}}}}}", str(v))
                self.tools.call("file_write", path=path, content=ctx.get("_rendered", ""))
                ctx["output_file"] = path
            elif action == "run_linter":
                f = params["file"]
                for k, v in ctx.items():
                    f = f.replace(f"{{{{{k}}}}}", str(v))
                self.tools.call("run_linter", file_path=f)
            elif action == "run_command":
                cmd = params["cmd"]
                for k, v in ctx.items():
                    cmd = cmd.replace(f"{{{{{k}}}}}", str(v))
                self.tools.call("run_command", cmd=cmd)


class DeterministicCodingAgent:
    """Parse → Reason → Execute → Audit. Zero LLM."""

    CONFIDENCE_THRESHOLD = 0.30

    def __init__(self, skills_root: str = "skill_packs", routes_path: Optional[str] = None):
        self.parser     = TaskParser()
        self.router     = MoERouter(routes_path or "swarm.yaml")
        self.tools      = ToolRegistry()
        self.executor   = SkillExecutor(self.tools)
        self.auditor    = DeterministicAuditor()
        self.scaffolder = MonteCarloScaffolder(self.executor, self.auditor)
        self.reasoner   = ReasoningEngine()
        
        self.skills_registry = get_skill_registry(skills_root)
        self.skills_registry.discover()
        self.skill_executor = get_skill_executor()
        # New integrations
        try:
            self.priority_engine = PriorityEngine()
        except Exception:
            self.priority_engine = None
        # conservative default: allow up to 6 concurrent units
        self.resource_allocator = ResourceAllocator(max_units=6)
        
        self.policy_engine = None
        try:
            from reasoning.policy_engine import get_policy_engine
            self.policy_engine = get_policy_engine()
        except ImportError:
            pass

        self.intent_router = None
        try:
            from orchestration.intent_router import IntentRouter
            self.intent_router = IntentRouter()

            # Wire standalone skill handlers (keyword-first parallel path)
            from skills.cli_anything import register_cli_anything_skill
            from skills.content_creation import register_content_creation_skill
            from skills.knowledge_synthesis import register_knowledge_synthesis_skill
            register_cli_anything_skill(self.intent_router)
            register_content_creation_skill(self.intent_router)
            register_knowledge_synthesis_skill(self.intent_router)

            # Wire hybrid engine intents as pass-through to standard DCA
            self.intent_router.register_intent(
                "support_ticket",
                ["ticket", "issue", "help", "broken"],
                self._intent_handler,
            )
            self.intent_router.register_intent(
                "process_email",
                ["email", "message", "inbox"],
                self._intent_handler,
            )
            self.intent_router.register_intent(
                "pr_review",
                ["review", "pull request", "pr", "code"],
                self._intent_handler,
            )
        except (ImportError, Exception):
            pass

    def _decision_scorer(self, choice: Dict) -> float:
        score = 0.0
        skill = str(choice.get("skill", "")).lower()
        if "react"   in skill: score += 0.6
        if "api"     in skill or "rest" in skill: score += 0.6
        if choice.get("lang")  == "typescript":   score += 0.2
        if choice.get("async") is True:            score += 0.1
        if choice.get("size")  in ("tiny","small"): score += 0.1
        return score

    def _build_constraints(self, task: Dict):
        return []

    def _variable_domains(self, task: Dict):
        return {}

    # ------------------------------------------------------------------ #
    # Session persistence
    # ------------------------------------------------------------------ #
    def _persist(self, state: Dict, user_input: str) -> Dict:
        try:
            from brain.state_manager import save_state, get_state_manager
            sm = get_state_manager()
            if not sm._current_session:
                sm._current_session = state["session_id"]
            sm.update_state(state)
            sm.append_history({
                "status": state.get("status", "unknown"),
                "skill":  state.get("reasoning", {}).get("chosen_skill", ""),
                "query":  user_input[:200],
            })
        except Exception as _e:
            logger.debug("Failed to persist session: %s", _e)
        return state

    # ------------------------------------------------------------------ #
    # Intent handler (pass-through to standard DCA)
    # ------------------------------------------------------------------ #
    def _intent_handler(self, query: str, context=None) -> None:
        return None

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def handle(self, user_input: str) -> Dict:
        task  = self.parser.parse(user_input)
        state = init_state(user_input, task)

        # ---- Intent router: keyword-first parallel path ----
        if self.intent_router:
            intent_result = self.intent_router.route_query(user_input, {"state": state, "query": user_input})
            if isinstance(intent_result, dict) and intent_result.get("status") == "success":
                state["status"] = "ok"
                state["final_output"] = intent_result
                state["intent_routed"] = True
                state["reasoning"] = {"chosen_skill": self.intent_router.classify_intent(user_input), "confidence": 1.0}
                return self._persist(state, user_input)

        # For unknown tasks, still run reasoning — the reasoner may find a match
        # via cosine similarity to available skills and NLU aliases.
        # Low-confidence guard below blocks execution if match is weak.

        # ---- Reasoning pipeline --------------------------------------
        # Build enriched candidates (skill_id → enriched text with aliases)
        enriched = self.router.enriched_candidates()
        text_to_id = {t: sid for sid, t in enriched}
        enriched_texts = [t for _, t in enriched]

        decision = self.reasoner.decide(
            task             = task,
            skill_candidates = enriched_texts,
            scorer_fn        = self._decision_scorer,
            constraints      = self._build_constraints(task),
            variable_domains = self._variable_domains(task),
        )
        # Map enriched text back to skill_id after ranking
        if decision.chosen_skill and decision.chosen_skill in text_to_id:
            decision.chosen_skill = text_to_id[decision.chosen_skill]

        # Boost: if task parser found a known task, prefer it
        parsed_task = task.get("task")
        if parsed_task and parsed_task != "unknown":
            if parsed_task in self.router.routes:
                decision.chosen_skill = parsed_task
                decision.confidence = max(decision.confidence, 0.85)

        state["reasoning"] = decision.to_dict()

        log_event("reasoning", {
            "session_id":    state["session_id"],
            "task":          task.get("task"),
            "chosen_skill":  decision.chosen_skill,
            "confidence":    decision.confidence,
            "audit_ok":      decision.audit_ok,
            "pre_audit":     decision.pre_audit,
            "status":        "ok" if decision.audit_ok else "blocked",
        })

        # ---- Pre-audit block -----------------------------------------
        if not decision.audit_ok:
            state["status"]       = "blocked"
            state["final_output"] = {
                "error":     "Pre-audit blocked execution",
                "issues":    decision.pre_audit,
                "reasoning": decision.to_dict(),
            }
            return self._persist(state, user_input)

        # ---- Policy gate — guardrail enforcement --------------------
        if self.policy_engine:
            policy_ctx = {
                "segment": task.get("raw", ""),
                "channel": decision.chosen_config.get("channel", "default"),
                "consent": {"email": True, "sms": True, "push": True, "in_app": True, "web": True},
                "recent_sends": {},
                "gdpr_consent": True,
            }
            gate = self.policy_engine.gate(decision.chosen_config, policy_ctx)
            state["policy_gate"] = gate.to_dict()
            if not gate.is_allowed:
                state["status"]       = "blocked"
                state["final_output"] = {
                    "error":     "Policy engine blocked execution",
                    "blocked_by": gate.blocked_by,
                    "reasoning": decision.to_dict(),
                }
                return self._persist(state, user_input)

        # ---- Low confidence — dynamic threshold ---------------------
        # When many candidates exist, cosine scores naturally dilute.
        # Scale threshold down logarithmically: log2(92) ≈ 6.5 → 0.30/6.5 ≈ 0.046
        n = len(enriched) if enriched else 1
        divisor = max(1, math.log(n, 2)) if n > 1 else 1
        effective_threshold = max(0.10, self.CONFIDENCE_THRESHOLD / divisor)
        if decision.confidence < effective_threshold:
            state["status"]       = "low_confidence"
            state["final_output"] = {
                "error":      f"Confidence {decision.confidence:.2f} below threshold "
                              f"{self.CONFIDENCE_THRESHOLD}",
                "reasoning":  decision.to_dict(),
            }
            return self._persist(state, user_input)

        # ---- No skill found — try bidirectional resolution ----------
        # Router uses hyphenated keys (e.g. "create-react-component")
        # Registry uses directory names (e.g. "react")
        # Bridge the gap with three strategies.
        skill_id = decision.chosen_skill
        if not skill_id or not self.skills_registry.get(skill_id):
            resolved = None

            # Strategy 1: router path leaf → registry skill_id
            route_path = self.router.routes.get(skill_id, "")
            if route_path:
                leaf = route_path.rstrip("/").split("/")[-1]
                if self.skills_registry.get(leaf):
                    resolved = leaf

            # Strategy 2: registry skill_id is substring of router key
            if not resolved:
                for meta in self.skills_registry.list_all():
                    if meta.skill_id in skill_id or skill_id in meta.skill_id:
                        resolved = meta.skill_id
                        break

            # Strategy 3: any word in skill_id matches registry skill_id
            if not resolved:
                words = set(skill_id.replace("-", " ").replace("_", " ").split())
                for meta in self.skills_registry.list_all():
                    meta_words = set(meta.skill_id.replace("-", " ").replace("_", " ").split())
                    if words & meta_words:
                        resolved = meta.skill_id
                        break

            if resolved:
                skill_id = resolved
            else:
                state["status"]       = "failed"
                state["final_output"] = {
                    "error":     f"No skill.md for '{skill_id}'",
                    "reasoning": decision.to_dict(),
                    "hint":      f"router path: '{route_path}'",
                }
                return self._persist(state, user_input)

        # ---- Execute via new orchestration --------------------------------
        skill_meta = self.skills_registry.get(skill_id)
        
        exec_inputs = {
            **task,
            **decision.chosen_config,
            "session_id": state["session_id"],
        }
        
        knowledge_context = []
        try:
            from knowledge.bank import get_knowledge_bank
            bank = get_knowledge_bank()
            if bank.loaded:
                fragments = bank.query(task.get("raw", task.get("task", "")), top_k=3)
                knowledge_context = [
                    {"title": f.source_title, "text": f.chunk_text, "tags": f.tags}
                    for f, score in fragments if f.confidence > 0.5
                ]
                exec_inputs["knowledge_context"] = knowledge_context
                state["knowledge_used"] = len(knowledge_context)
        except Exception:
            pass
        
        try:
            from brain.soul import get_soul
            soul = get_soul()
            if soul.name:
                soul.merge_into_exec_inputs(exec_inputs)
                state["soul_loaded"] = True
        except Exception:
            pass
        
        context = {
            "session_id": state["session_id"],
            "skill_configs": {},
        }
        
        # ---- Priority rerank & Resource allocation --------------------
        # Build a small candidate set: chosen skill + up to 3 related skills
        try:
            if self.priority_engine and skill_meta:
                candidates = []
                candidates.append({"id": skill_meta.skill_id, "arm_id": skill_meta.skill_id,
                                   "text": getattr(skill_meta, "description", skill_meta.skill_id)})
                # pick up to 3 other candidates sharing tokens
                added = {skill_meta.skill_id}
                for meta in self.skills_registry.list_all():
                    if len(candidates) >= 4:
                        break
                    sid = meta.skill_id
                    if sid in added:
                        continue
                    # simple token overlap heuristic
                    if any(tok in sid for tok in skill_id.replace("-", " ").split()):
                        candidates.append({"id": sid, "arm_id": sid, "text": getattr(meta, "description", sid)})
                        added.add(sid)

                chosen = self.priority_engine.choose(candidates, {"query": task.get("raw", "")})
                if chosen and chosen[0].get("id") != skill_id:
                    # override skill selection if priority engine prefers alternative
                    skill_id = chosen[0].get("id")
                    skill_meta = self.skills_registry.get(skill_id)
        except Exception:
            pass

        # ---- Monte Carlo scaffolded execution ------------------------
        if skill_meta and skill_meta.monte_carlo and skill_meta.choices:
            mc_inputs = {**exec_inputs, "skill_path": skill_meta.skill_path}
            result = self.scaffolder.scaffold(skill_meta.to_dict(), mc_inputs)
            state["monte_carlo_used"] = True
        else:
            # Allocate a unit before executing to avoid resource exhaustion
            alloc_key = state.get("session_id") or "global"
            with self.resource_allocator.allocating(alloc_key, units=1, timeout=2) as ok:
                if not ok:
                    state["status"] = "resource_starved"
                    state["final_output"] = {"error": "Resource allocation timeout"}
                    return self._persist(state, user_input)
                result = self.skill_executor.execute(skill_id, exec_inputs, context)

        state["final_output"] = result
        state["status"]       = "ok" if result.get("success") else "failed"
        state["score"]        = decision.confidence

        log_event("handle", {
            "session_id": state["session_id"],
            "task":       task["task"],
            "status":     state["status"],
            "skill":      skill_id,
            "confidence": decision.confidence,
        })
        return self._persist(state, user_input)

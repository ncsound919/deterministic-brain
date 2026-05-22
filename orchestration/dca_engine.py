"""DeterministicCodingAgent — no-LLM core loop wired to ReasoningEngine."""
from __future__ import annotations
import glob
import math
import os
import re
import threading
import time
from contextlib import contextmanager

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
from reasoning.context_graph import get_context_graph
from tools.registry import ToolRegistry
from tools.tracing import log_event

from orchestration import get_skill_registry, get_skill_executor
from reasoning.priority_engine import PriorityEngine
from orchestration.resource_allocator import ResourceAllocator
from orchestration.confidence_routing import MultiLayerConfidenceRouter
from orchestration.event_bus import event_bus, connect_all_learning
from tools.tracing import checkpoint_state

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Timeout wrapper for skill execution (cross-platform: Windows + Unix)
# -------------------------------------------------------------------
class TimeoutException(Exception):
    pass


@contextmanager
def timeout(seconds: int):
    """Cross-platform timeout using threading.Timer + _thread.interrupt_main."""
    import _thread

    timer = None

    def _raise_timeout():
        _thread.interrupt_main()

    timer = threading.Timer(seconds, _raise_timeout)
    timer.daemon = True
    timer.start()
    try:
        yield
    except KeyboardInterrupt:
        timer.cancel()
        raise TimeoutException(f"Operation timed out after {seconds}s")
    finally:
        if timer:
            timer.cancel()


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
        log_event(
            "step",
            {"skill": skill_path, "actions": [a for a, _ in step], "session_id": ctx.get("session_id")},
        )
        auditor = DeterministicAuditor()
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
                    actions.append(("render_template", {"template": m.group(1)}))
                    continue
                m = _RE_WRITE_RESULT.match(line)
                if m:
                    actions.append(("file_write", {"path": m.group(1)}))
                    continue
                m = _RE_RUN_LINTER.match(line)
                if m:
                    actions.append(("run_linter", {"file": m.group(1)}))
                    continue
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

                env = Environment(loader=FileSystemLoader("."))
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
    SKILL_EXECUTION_TIMEOUT_SECONDS = 300  # FIX: 5 minutes timeout

    def __init__(self, skills_root: str = "skill_packs", routes_path: Optional[str] = None):
        self._shutdown_check = lambda: False
        self.parser = TaskParser()
        self.router = MoERouter(routes_path or "swarm.yaml")
        self.tools = ToolRegistry()
        self.executor = SkillExecutor(self.tools)
        self.auditor = DeterministicAuditor()
        self.scaffolder = MonteCarloScaffolder(self.executor, self.auditor)
        self.reasoner = ReasoningEngine()
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

            # FIX: Wire hybrid engine intents to full DCA handle loop (NOT returning None)
            self.intent_router.register_intent(
                "support_ticket",
                ["ticket", "issue", "help", "broken"],
                lambda query, ctx: self._handle_via_dca(query),
            )
            self.intent_router.register_intent(
                "process_email",
                ["email", "message", "inbox"],
                lambda query, ctx: self._handle_via_dca(query),
            )
            self.intent_router.register_intent(
                "pr_review",
                ["review", "pull request", "pr", "code"],
                lambda query, ctx: self._handle_via_dca(query),
            )
        except (ImportError, Exception) as e:
            logger.debug("Intent router not wired: %s", e)

        # Hybrid confidence stacking (lazy-registered on first handle)
        self.confidence_router = MultiLayerConfidenceRouter()
        try:
            self.context_graph = get_context_graph()
        except Exception as e:
            logger.debug("Context graph not wired: %s", e)
            self.context_graph = None

        # Wire EventBus learning loop (SkillEvolver + RuntimeHealer)
        try:
            connect_all_learning()
        except Exception as e:
            logger.debug("Learning loop not wired: %s", e)

        # Wire TaskQueue as a background handler
        try:
            from tools.task_queue import get_task_queue
            self.task_queue = get_task_queue()
            self.task_queue.register_handler("process_task", self.handle)
            if os.environ.get("TASK_WORKER", "").lower() in ("1", "true", "yes"):
                self.task_queue.start_worker("default")
        except Exception as e:
            logger.debug("Task queue not wired: %s", e)
            self.task_queue = None

    def register_shutdown_check(self, check_fn):
        """Register a callable that returns True if shutdown is requested."""
        self._shutdown_check = check_fn

    def _handle_via_dca(self, query: str) -> Dict:
        """FIX: Intent handler now delegates to full DCA handle loop."""
        return self.handle(query)

    def _decision_scorer(self, choice: Dict) -> float:
        score = 0.0
        skill = str(choice.get("skill", "")).lower()
        if "react" in skill:
            score += 0.6
        if "api" in skill or "rest" in skill:
            score += 0.6
        if choice.get("lang") == "typescript":
            score += 0.2
        if choice.get("async") is True:
            score += 0.1
        if choice.get("size") in ("tiny", "small"):
            score += 0.1
        return score

    def _stack_confidence(self, decision, task: Dict, enriched: list, state: Dict):
        """Layer L1 (rule-based) + L2 (semantic) + L3 (evidence) into stacked confidence."""
        skill_id = decision.chosen_skill
        l1_score = decision.confidence if decision.confidence > 0 else 0.5

        # L2: semantic similarity from knowledge bank
        l2_score = 0.5
        try:
            from knowledge.bank import get_knowledge_bank
            bank = get_knowledge_bank()
            if bank.loaded:
                raw = task.get("raw", task.get("task", ""))
                fragments = bank.query(raw, top_k=3) if raw else []
                if fragments:
                    l2_score = sum(getattr(f, "confidence", 0.5) for f, _ in fragments) / len(fragments)
        except Exception:
            pass

        # L3: evidence from session history
        l3_score = 0.5
        try:
            sid = state.get("session_id", "")
            if sid:
                session_data = sm.load_session(sid)
                history = session_data.get("history", []) if session_data else []
                if history:
                    successes = sum(1 for h in history if h.get("status") == "ok")
                    l3_score = min(1.0, successes / max(len(history), 1))
        except Exception:
            pass

        # L3b: bias from ContextGraph causal history
        try:
            if self.context_graph and skill_id:
                raw_text = task.get("raw", task.get("task", ""))
                historical = self.context_graph.why_this_skill(
                    raw_text[:200], skill_id
                )
                sample_count = historical.get("sample_count", 0)
                factor_weights = historical.get("factor_weights", {})
                if sample_count > 0 and factor_weights:
                    avg_weight = sum(factor_weights.values()) / max(len(factor_weights), 1)
                    # Blend: L3 (session-local) + CG (cross-session historical)
                    l3_score = 0.7 * l3_score + 0.3 * min(1.0, avg_weight)
        except Exception:
            pass

        # Only apply stacking if router has a matching route
        route_name = skill_id or "default"
        if route_name not in self.confidence_router.routes:
            def passthrough_primary(x):
                return x, l1_score
            self.confidence_router.register_route(
                route_name,
                primary_fn=passthrough_primary,
                fallback_fn=lambda x: x,
                semantic_fn=lambda x: l2_score,
                evidence_fn=lambda x: l3_score,
            )

        raw_query = task.get("raw", task.get("task", ""))
        result = self.confidence_router.execute(
            route_name, raw_query,
            semantic_score=l2_score,
            evidence_score=l3_score,
        )

        if result.layer_scores:
            decision.confidence = result.layer_scores["final"]
            state["confidence_stacked"] = {
                "layer_scores": result.layer_scores,
                "weights_used": result.weights_used,
                "fallback_triggered": result.fallback_triggered,
            }

    def _build_constraints(self, task: Dict):
        constraints = []
        task_type = task.get("task", "")
        raw_text = task.get("raw", "")

        # Security: no dangerous patterns in generated code
        constraints.append(
            Constraint(
                "allow_eval",
                lambda v: v is False,
                "eval() is prohibited for security",
            )
        )
        constraints.append(
            Constraint(
                "allow_shell",
                lambda v: v is False,
                "shell=True is prohibited for security",
            )
        )

        # Resource limits must be positive
        constraints.append(
            Constraint(
                "memory_limit",
                lambda v: v is None or v > 0,
                "Memory limit must be positive if set",
            )
        )
        constraints.append(
            Constraint(
                "timeout",
                lambda v: v is None or v > 0,
                "Timeout must be positive if set",
            )
        )

        # Auth requirement
        if task.get("requires_auth"):
            constraints.append(
                Constraint(
                    "auth_enabled",
                    lambda v: v is True,
                    "Task requires authentication",
                )
            )

        # Security tasks must use SSL
        if "security" in task_type.lower():
            constraints.append(
                Constraint(
                    "use_ssl",
                    lambda v: v is True,
                    "Security tasks must use SSL",
                )
            )

        # File operations must not traverse outside project
        if "file" in task_type.lower() or "write" in task_type.lower():
            constraints.append(
                Constraint(
                    "allow_path_traversal",
                    lambda v: v is False,
                    "Path traversal is prohibited",
                )
            )

        # Learned constraints from RuntimeHealer corrections
        try:
            from orchestration.runtime_healer import runtime_healer
            for lc in runtime_healer.get_learned_constraints():
                pattern = lc.get("pattern", "")
                skill_ref = lc.get("skill_id", "")
                if pattern and skill_ref:
                    constraints.append(
                        Constraint(
                            f"healer_{skill_ref}",
                            lambda v, p=pattern: p.lower() not in str(v).lower() if v else True,
                            f"Healer learned constraint: avoid '{pattern[:80]}' from {skill_ref}",
                        )
                    )
        except Exception:
            pass

        return constraints

    def _variable_domains(self, task: Dict):
        domains = {}
        task_type = task.get("task", "")

        # All tasks define security posture
        domains["allow_eval"] = [False]
        domains["allow_shell"] = [False]
        domains["memory_limit"] = [None, 128, 256, 512]
        domains["timeout"] = [None, 30, 60, 120, 300]
        domains["auth_enabled"] = [True, False]
        domains["use_ssl"] = [True, False]
        domains["allow_path_traversal"] = [False]

        # Task-specific domains
        if task_type == "deploy":
            domains["environment"] = ["dev", "staging", "prod"]
            domains["rollback_strategy"] = ["immediate", "gradual", "manual"]
        elif task_type in ("create-api", "scaffold"):
            domains["framework"] = ["fastapi", "express", "flask", "gin"]
            domains["database"] = ["none", "postgres", "sqlite", "mysql"]
        elif task_type in ("create-react-component", "ui"):
            domains["framework"] = ["react", "vue", "svelte"]
            domains["styling"] = ["css", "tailwind", "styled-components"]
        elif task_type == "docker":
            domains["base_image"] = ["python:3.11-slim", "node:20-alpine", "alpine:latest"]

        if task.get("framework"):
            domains["framework_version"] = ["latest", "stable", "lts"]

        return domains

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def _persist(self, state: Dict, user_input: str) -> Dict:
        try:
            from brain.state_manager import save_state, get_state_manager

            sm = get_state_manager()
            if not sm._current_session:
                sm._current_session = state["session_id"]
            sm.update_state(state)
            sm.append_history(
                {
                    "status": state.get("status", "unknown"),
                    "skill": state.get("reasoning", {}).get("chosen_skill", ""),
                    "query": user_input[:200],
                }
            )
        except Exception as _e:
            logger.debug("Failed to persist session: %s", _e)
        return state

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def handle(self, user_input: str) -> Dict:
        if self._shutdown_check():
            return {
                "status": "shutdown",
                "final_output": {"error": "Shutdown in progress — rejecting new work"},
            }
        task = self.parser.parse(user_input)
        state = init_state(user_input, task)
        checkpoint_state("parse", state)

        # ---- Intent router: keyword-first parallel path ----
        if self.intent_router:
            intent_result = self.intent_router.route_query(user_input, {"state": state, "query": user_input})
            if isinstance(intent_result, dict) and intent_result.get("status") == "success":
                state["status"] = "ok"
                state["final_output"] = intent_result
                state["intent_routed"] = True
                state["reasoning"] = {
                    "chosen_skill": self.intent_router.classify_intent(user_input),
                    "confidence": 1.0,
                }
                return self._persist(state, user_input)

        # ---- Reasoning pipeline --------------------------------------
        enriched = self.router.enriched_candidates()
        text_to_id = {t: sid for sid, t in enriched}
        enriched_texts = [t for _, t in enriched]

        decision = self.reasoner.decide(
            task=task,
            skill_candidates=enriched_texts,
            scorer_fn=self._decision_scorer,
            constraints=self._build_constraints(task),
            variable_domains=self._variable_domains(task),
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
        checkpoint_state("reasoning", state)
        log_event(
            "reasoning",
            {
                "session_id": state["session_id"],
                "task": task.get("task"),
                "chosen_skill": decision.chosen_skill,
                "confidence": decision.confidence,
                "audit_ok": decision.audit_ok,
                "pre_audit": decision.pre_audit,
                "status": "ok" if decision.audit_ok else "blocked",
            },
        )

        # ---- Hybrid confidence stacking ------------------------------
        self._stack_confidence(decision, task, enriched, state)
        checkpoint_state("confidence", state)

        # Record decision in context graph for causal analysis
        try:
            cg = self.context_graph
            if cg and decision.chosen_skill:
                stacked = state.get("confidence_stacked", {})
                factors = {}
                if stacked.get("layer_scores"):
                    for k, v in stacked["layer_scores"].items():
                        factors[k] = v
                if not factors:
                    factors["l1_raw"] = decision.confidence
                    factors["n_candidates"] = len(enriched) if enriched else 1
                cg.record_decision(
                    session_id=state.get("session_id", ""),
                    decision_type="skill_selection",
                    factors=factors,
                    outcome="accepted" if decision.audit_ok else "rejected",
                    chosen=decision.chosen_skill,
                    confidence=decision.confidence,
                )
        except Exception as e:
            logger.debug("Context graph record failed: %s", e)

        # ---- Pre-audit block -----------------------------------------
        if not decision.audit_ok:
            state["status"] = "blocked"
            state["final_output"] = {
                "error": "Pre-audit blocked execution",
                "issues": decision.pre_audit,
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
                state["status"] = "blocked"
                state["final_output"] = {
                    "error": "Policy engine blocked execution",
                    "blocked_by": gate.blocked_by,
                    "reasoning": decision.to_dict(),
                }
                return self._persist(state, user_input)

        # ---- Low confidence — dynamic threshold ---------------------
        n = len(enriched) if enriched else 1
        divisor = max(1, math.log(n, 2)) if n > 1 else 1
        effective_threshold = max(0.10, self.CONFIDENCE_THRESHOLD / divisor)

        if decision.confidence < effective_threshold:
            state["status"] = "low_confidence"
            state["final_output"] = {
                "error": f"Confidence {decision.confidence:.2f} below threshold {self.CONFIDENCE_THRESHOLD}",
                "reasoning": decision.to_dict(),
            }
            return self._persist(state, user_input)

        # ---- No skill found — try bidirectional resolution ----------
        skill_id = decision.chosen_skill
        if not skill_id or not self.skills_registry.get(skill_id):
            resolved = None
            route_path = self.router.routes.get(skill_id, "")
            if route_path:
                leaf = route_path.rstrip("/").split("/")[-1]
                if self.skills_registry.get(leaf):
                    resolved = leaf
            if not resolved:
                for meta in self.skills_registry.list_all():
                    if meta.skill_id in skill_id or skill_id in meta.skill_id:
                        resolved = meta.skill_id
                        break
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
                state["status"] = "failed"
                state["final_output"] = {
                    "error": f"No skill.md for '{skill_id}'",
                    "reasoning": decision.to_dict(),
                    "hint": f"router path: '{route_path}'",
                }
                return self._persist(state, user_input)

        # ---- Execute via new orchestration ----------------------------
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
                    for f, score in fragments
                    if f.confidence > 0.5
                ]
            exec_inputs["knowledge_context"] = knowledge_context
            state["knowledge_used"] = len(knowledge_context)
        except Exception as e:
            logger.debug("Knowledge bank unavailable: %s", e)

        try:
            from brain.soul import get_soul

            soul = get_soul()
            if soul.name:
                soul.merge_into_exec_inputs(exec_inputs)
                state["soul_loaded"] = True
        except Exception as e:
            logger.debug("Soul not loaded: %s", e)

        context = {
            "session_id": state["session_id"],
            "skill_configs": {},
        }

        # ---- Priority rerank & Resource allocation --------------------
        try:
            if self.priority_engine and skill_meta:
                candidates = []
                candidates.append(
                    {
                        "id": skill_meta.skill_id,
                        "arm_id": skill_meta.skill_id,
                        "text": getattr(skill_meta, "description", skill_meta.skill_id),
                    }
                )
                added = {skill_meta.skill_id}
                for meta in self.skills_registry.list_all():
                    if len(candidates) >= 4:
                        break
                    sid = meta.skill_id
                    if sid in added:
                        continue
                    if any(tok in sid for tok in skill_id.replace("-", " ").split()):
                        candidates.append(
                            {"id": sid, "arm_id": sid, "text": getattr(meta, "description", sid)}
                        )
                        added.add(sid)
                chosen = self.priority_engine.choose(candidates, {"query": task.get("raw", "")})
                if chosen and chosen[0].get("id") != skill_id:
                    skill_id = chosen[0].get("id")
                    skill_meta = self.skills_registry.get(skill_id)
        except Exception as e:
            logger.debug("Priority engine failed: %s", e)

        # ---- Monte Carlo scaffolded execution ------------------------
        if skill_meta and skill_meta.monte_carlo and skill_meta.choices:
            mc_inputs = {**exec_inputs, "skill_path": skill_meta.skill_path}
            result = self.scaffolder.scaffold(skill_meta.to_dict(), mc_inputs)
            state["monte_carlo_used"] = True
        else:
            alloc_key = state.get("session_id") or "global"
            with self.resource_allocator.allocating(alloc_key, units=1, timeout=2) as ok:
                if not ok:
                    state["status"] = "resource_starved"
                    state["final_output"] = {"error": "Resource allocation timeout"}
                    return self._persist(state, user_input)

                # FIX: Wrap skill execution in timeout
                try:
                    with timeout(self.SKILL_EXECUTION_TIMEOUT_SECONDS):
                        result = self.skill_executor.execute(skill_id, exec_inputs, context)
                except TimeoutException as te:
                    logger.error("Skill execution timeout: %s", te)
                    state["status"] = "timeout"
                    state["final_output"] = {"error": str(te)}
                    return self._persist(state, user_input)

        state["final_output"] = result
        state["status"] = "ok" if result.get("success") else "failed"
        state["score"] = decision.confidence
        checkpoint_state("execute", state)
        log_event(
            "handle",
            {
                "session_id": state["session_id"],
                "task": task["task"],
                "status": state["status"],
                "skill": skill_id,
                "confidence": decision.confidence,
            },
        )

        # Emit skill execution events for EventBus learning loop
        try:
            latency_ms = int((time.time() - getattr(self, "_exec_start", time.time())) * 1000)
            if state["status"] == "ok":
                event_bus.emit("skill_success", skill_id=skill_id, latency_ms=latency_ms, confidence=decision.confidence)
            else:
                event_bus.emit("skill_failure", skill_id=skill_id, latency_ms=latency_ms, confidence=decision.confidence)
        except Exception as e:
            logger.debug("EventBus emission failed: %s", e)

        return self._persist(state, user_input)

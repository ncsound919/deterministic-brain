"""DeterministicCodingAgent — no-LLM core loop wired to ReasoningEngine."""
from __future__ import annotations
import glob
import os
import re
import yaml
from typing import Dict, List, Optional

from brain.task_parser import TaskParser
from brain.router import MoERouter
from brain.memory import init_state
from planners.monte_carlo import MonteCarloScaffolder
from reasoning.auditor import DeterministicAuditor
from reasoning.math_engine import ReasoningEngine, Constraint
from tools.registry import ToolRegistry
from tools.tracing import log_event

from orchestration import get_skill_registry, get_skill_executor, SkillExecutor


class SkillExecutor:
    def __init__(self, tool_registry: ToolRegistry):
        self.tools = tool_registry

    def execute(self, skill_path: str, inputs: Dict) -> Dict:
        with open(skill_path) as f:
            content = f.read()
        if not content.startswith("---"):
            raise ValueError(f"Invalid skill.md — {skill_path}")
        _, fm, md_body = content.split("---", 2)
        meta = yaml.safe_load(fm)
        for t in meta.get("tools", []):
            if not self.tools.has(t):
                raise ValueError(f"Tool '{t}' not in registry")
        ctx = {**inputs}
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
        for block in re.split(r"## Step \d+", md_body)[1:]:
            actions = []
            for line in block.strip().splitlines():
                line = line.strip()
                m = re.match(r"Render template `(.+?)` with context", line)
                if m:
                    actions.append(("render_template", {"template": m.group(1)})); continue
                m = re.match(r"Write result to `(.+?)`", line)
                if m:
                    actions.append(("file_write", {"path": m.group(1)})); continue
                m = re.match(r"Run linter on `(.+?)`", line)
                if m:
                    actions.append(("run_linter", {"file": m.group(1)})); continue
                m = re.match(r"Run command `(.+?)`", line)
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
        
        self._legacy_skills_map = self._build_legacy_map()

    def _build_legacy_map(self) -> Dict[str, str]:
        mapping = {}
        for skill in self.skills_registry.list_all():
            mapping[skill.skill_id] = skill.skill_id
            mapping[skill.skill_name] = skill.skill_id
        return mapping

    @property
    def skills(self) -> Dict[str, str]:
        return self._legacy_skills_map

    # ------------------------------------------------------------------ #
    # Reasoning helpers (exposed so /reason endpoint can call them)
    # ------------------------------------------------------------------ #

    def _build_constraints(self, task: Dict) -> List[Constraint]:
        raw = task.get("raw", "").lower()
        out: List[Constraint] = []
        if "typescript" in raw:
            out.append(Constraint("lang",  lambda v: v == "typescript",  "force typescript"))
        elif "python" in raw:
            out.append(Constraint("lang",  lambda v: v == "python",      "force python"))
        if "async" in raw:
            out.append(Constraint("async", lambda v: v is True,          "must be async"))
        elif "sync" in raw:
            out.append(Constraint("async", lambda v: v is False,         "must be sync"))
        if any(w in raw for w in ("small", "minimal", "tiny", "lean")):
            out.append(Constraint("size",  lambda v: v in {"small","tiny"}, "small size"))
        return out

    def _variable_domains(self, _task: Dict) -> Dict[str, List]:
        return {
            "lang":  ["python", "typescript"],
            "async": [True, False],
            "size":  ["tiny", "small", "medium"],
        }

    def _decision_scorer(self, choice: Dict) -> float:
        score = 0.0
        skill = str(choice.get("skill", "")).lower()
        if "react"   in skill: score += 0.6
        if "api"     in skill or "rest" in skill: score += 0.6
        if choice.get("lang")  == "typescript":   score += 0.2
        if choice.get("async") is True:            score += 0.1
        if choice.get("size")  in ("tiny","small"): score += 0.1
        return score

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def handle(self, user_input: str) -> Dict:
        task  = self.parser.parse(user_input)
        state = init_state(user_input, task)

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
            return state

        # ---- Low confidence — dynamic threshold ---------------------
        # When many candidates exist, cosine scores naturally dilute.
        # Scale threshold down logarithmically: log2(92) ≈ 6.5 → 0.30/6.5 ≈ 0.046
        import math as _math
        n = len(enriched) if enriched else 1
        divisor = max(1, _math.log(n, 2)) if n > 1 else 1
        effective_threshold = max(0.10, self.CONFIDENCE_THRESHOLD / divisor)
        if decision.confidence < effective_threshold:
            state["status"]       = "low_confidence"
            state["final_output"] = {
                "error":      f"Confidence {decision.confidence:.2f} below threshold "
                              f"{self.CONFIDENCE_THRESHOLD}",
                "reasoning":  decision.to_dict(),
            }
            return state

        # ---- No skill found — try path-based resolution --------
        skill_id = decision.chosen_skill
        if not skill_id or not self.skills_registry.get(skill_id):
            # Resolve route key → registry ID via path matching
            resolved = None
            for meta in self.skills_registry.list_all():
                if meta.path and skill_id in meta.path:
                    resolved = meta.skill_id
                    break
            if resolved:
                skill_id = resolved
            else:
                state["status"]       = "failed"
                state["final_output"] = {
                    "error":     f"No skill.md for '{skill_id}'",
                    "reasoning": decision.to_dict(),
                }
                return state

        # ---- Execute via new orchestration --------------------------------
        skill_meta = self.skills_registry.get(skill_id)
        
        exec_inputs = {
            **task,
            **decision.chosen_config,
            "session_id": state["session_id"],
        }
        
        context = {
            "session_id": state["session_id"],
            "skill_configs": {},
        }
        
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
        return state

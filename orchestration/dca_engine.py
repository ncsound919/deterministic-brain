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
        self.router     = MoERouter(routes_path)
        self.tools      = ToolRegistry()
        self.executor   = SkillExecutor(self.tools)
        self.auditor    = DeterministicAuditor()
        self.scaffolder = MonteCarloScaffolder(self.executor, self.auditor)
        self.reasoner   = ReasoningEngine()
        self.skills     = self._index_skills(skills_root)

    # ------------------------------------------------------------------ #
    # Skill index
    # ------------------------------------------------------------------ #

    def _index_skills(self, root: str) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for path in glob.glob(os.path.join(root, "**/*.skill.md"), recursive=True):
            try:
                with open(path) as f:
                    content = f.read()
                if content.startswith("---"):
                    meta = yaml.safe_load(content.split("---")[1])
                    mapping[meta["skill"]] = path
            except Exception:
                pass
        return mapping

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

        # ---- Unknown task fast-exit -----------------------------------
        if task["task"] == "unknown":
            state["status"]       = "failed"
            state["final_output"] = {"error": "Unrecognized task", "raw": user_input}
            return state

        # ---- Reasoning pipeline --------------------------------------
        decision = self.reasoner.decide(
            task             = task,
            skill_candidates = list(self.skills.keys()),
            scorer_fn        = self._decision_scorer,
            constraints      = self._build_constraints(task),
            variable_domains = self._variable_domains(task),
        )
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

        # ---- Low confidence ------------------------------------------
        if decision.confidence < self.CONFIDENCE_THRESHOLD:
            state["status"]       = "low_confidence"
            state["final_output"] = {
                "error":      f"Confidence {decision.confidence:.2f} below threshold "
                              f"{self.CONFIDENCE_THRESHOLD}",
                "reasoning":  decision.to_dict(),
            }
            return state

        # ---- No skill found ------------------------------------------
        skill_path = self.skills.get(decision.chosen_skill or "")
        if not skill_path:
            state["status"]       = "failed"
            state["final_output"] = {
                "error":     f"No skill.md for '{decision.chosen_skill}'",
                "reasoning": decision.to_dict(),
            }
            return state

        # ---- Execute -------------------------------------------------
        with open(skill_path) as f:
            meta = yaml.safe_load(f.read().split("---")[1])
        meta["skill_path"] = skill_path

        exec_inputs = {
            **task,
            **decision.chosen_config,
            "session_id": state["session_id"],
        }

        result = (
            self.scaffolder.scaffold(meta, exec_inputs)
            if meta.get("monte_carlo")
            else self.executor.execute(skill_path, exec_inputs)
        )

        state["final_output"] = result
        state["status"]       = "ok" if result.get("success") else "failed"
        state["score"]        = decision.confidence

        log_event("handle", {
            "session_id": state["session_id"],
            "task":       task["task"],
            "status":     state["status"],
            "skill":      decision.chosen_skill,
            "confidence": decision.confidence,
        })
        return state

"""DeterministicCodingAgent — the no-LLM core loop."""
from __future__ import annotations
import glob
import os
import re
import yaml
from typing import Dict, Any

from brain.task_parser import TaskParser
from brain.router import MoERouter
from brain.memory import init_state
from planners.monte_carlo import MonteCarloScaffolder
from reasoning.auditor import DeterministicAuditor
from tools.registry import ToolRegistry
from tools.tracing import log_event


class SkillExecutor:
    """Interprets skill.md YAML steps and calls registered tools."""

    def __init__(self, tool_registry: ToolRegistry):
        self.tools = tool_registry

    def execute(self, skill_path: str, inputs: Dict) -> Dict:
        with open(skill_path) as f:
            content = f.read()
        if not content.startswith("---"):
            raise ValueError(f"Invalid skill.md: missing frontmatter — {skill_path}")
        _, fm, md_body = content.split("---", 2)
        meta = yaml.safe_load(fm)

        # validate tools
        for t in meta.get("tools", []):
            if not self.tools.has(t):
                raise ValueError(f"Tool '{t}' not in registry")

        ctx = {**inputs}
        steps = self._parse_steps(md_body)
        for step in steps:
            self._execute_step(step, ctx)
            log_event("step", {"skill": skill_path, "actions": [a for a, _ in step]})

        auditor = DeterministicAuditor()
        audit_ok = auditor.run_audit(meta.get("audit", []), ctx)
        if audit_ok:
            return {"success": True,  "output": ctx.get("output_file", ""), "ctx": ctx}
        return  {"success": False, "errors": "Audit failed", "ctx": ctx}

    # ------------------------------------------------------------------ #
    def _parse_steps(self, md_body: str):
        steps = []
        for block in re.split(r"## Step \d+", md_body)[1:]:
            actions = []
            for line in block.strip().splitlines():
                line = line.strip()
                m = re.match(r"Render template `(.+?)` with context", line)
                if m:
                    actions.append(("render_template", {"template": m.group(1)}))
                    continue
                m = re.match(r"Write result to `(.+?)`", line)
                if m:
                    actions.append(("file_write", {"path": m.group(1)}))
                    continue
                m = re.match(r"Run linter on `(.+?)`", line)
                if m:
                    actions.append(("run_linter", {"file": m.group(1)}))
                    continue
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
                env = Environment(loader=FileSystemLoader("."))
                tmpl = env.get_template(params["template"])
                ctx["_rendered"] = tmpl.render(**ctx)
            elif action == "file_write":
                path = params["path"].format(**ctx)
                self.tools.call("file_write", path=path, content=ctx.get("_rendered", ""))
                ctx["output_file"] = path
            elif action == "run_linter":
                f = params["file"].format(**ctx)
                self.tools.call("run_linter", file_path=f)
            elif action == "run_command":
                cmd = params["cmd"].format(**ctx)
                self.tools.call("run_command", cmd=cmd)


class DeterministicCodingAgent:
    """Top-level agent: parse → route → execute/scaffold → audit."""

    def __init__(self, skills_root: str = "skill_packs", routes_path: str | None = None):
        self.parser    = TaskParser()
        self.router    = MoERouter(routes_path)
        self.tools     = ToolRegistry()
        self.executor  = SkillExecutor(self.tools)
        self.auditor   = DeterministicAuditor()
        self.scaffolder= MonteCarloScaffolder(self.executor, self.auditor)
        self.skills    = self._index_skills(skills_root)

    def _index_skills(self, root: str) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for path in glob.glob(os.path.join(root, "**/*.skill.md"), recursive=True):
            try:
                with open(path) as f:
                    content = f.read()
                if content.startswith("---"):
                    fm = content.split("---")[1]
                    meta = yaml.safe_load(fm)
                    mapping[meta["skill"]] = path
            except Exception:
                pass
        return mapping

    def handle(self, user_input: str) -> Dict:
        task  = self.parser.parse(user_input)
        state = init_state(user_input, task)

        if task["task"] == "unknown":
            return {"error": "Unrecognized task", "raw": user_input}

        expert = self.router.route(task)
        if not expert:
            return {"error": f"No expert for task '{task['task']}'", **state}

        skill_path = self.skills.get(task["task"])
        if not skill_path:
            return {"error": f"No skill.md for {task['task']}", **state}

        with open(skill_path) as f:
            fm = f.read().split("---")[1]
        meta = yaml.safe_load(fm)
        meta["skill_path"] = skill_path

        if meta.get("monte_carlo"):
            result = self.scaffolder.scaffold(meta, task)
        else:
            result = self.executor.execute(skill_path, task)

        state["final_output"] = result
        state["status"]       = "ok" if result.get("success") else "failed"
        log_event("handle", {"task": task["task"], "status": state["status"]})
        return state

"""Skill backend adapters — unified interface for local and external skill systems."""
from __future__ import annotations
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SkillBackend(ABC):
    """Abstract base class for all skill backends."""

    @abstractmethod
    def run(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        """Execute a skill and return result.

        Args:
            skill_id: The skill identifier (local path or external ID)
            task: Task dict with 'raw', 'task', and extracted params
            context: Execution context including session state, configs

        Returns:
            Dict with keys: success (bool), output (str), artifacts (list), logs (list)
        """
        pass

    @abstractmethod
    def list_skills(self) -> list[Dict[str, str]]:
        """List available skills from this backend.

        Returns:
            List of {id, name, description} for each available skill
        """
        pass

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Identifier for this backend (local, claude, openclaw, hermes)."""
        pass


class LocalSkillBackend(SkillBackend):
    """Execute skills locally using deterministic templates."""

    def __init__(self, skill_packs_root: Optional[str] = None):
        self.skill_packs_root = skill_packs_root or self._get_default_root()

    def _get_default_root(self) -> str:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "skill_packs")

    @property
    def backend_name(self) -> str:
        return "local"

    def run(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        from tools.file_io import file_write, file_read
        from jinja2 import Template

        skill_path = os.path.join(self.skill_packs_root, skill_id, "skill.md")
        if not os.path.exists(skill_path):
            return {
                "success": False,
                "output": f"Skill not found: {skill_id}",
                "artifacts": [],
                "logs": [f"ERROR: skill.md not found at {skill_path}"],
            }

        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()

        front_matter, steps = self._parse_skill_md(content)
        if not steps:
            return {
                "success": False,
                "output": "No executable steps found in skill",
                "artifacts": [],
                "logs": [],
            }

        artifacts = []
        logs = []

        for i, step in enumerate(steps):
            logs.append(f"Executing step {i+1}: {step.get('description', 'unnamed')}")

            if step.get("template"):
                template_text = self._load_template(skill_id, step["template"])
                if template_text:
                    try:
                        tmpl = Template(template_text)
                        rendered = tmpl.render(**task)
                        output_path = step.get("output", f"output/{skill_id}/step{i+1}.txt")
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        file_write(output_path, rendered)
                        artifacts.append({"path": output_path, "type": "file"})
                        logs.append(f"Wrote {output_path}")
                    except Exception as e:
                        logs.append(f"Template error: {e}")
            elif step.get("command"):
                logs.append(f"Would execute: {step['command']}")

        return {
            "success": True,
            "output": f"Executed {len(steps)} steps for skill {skill_id}",
            "artifacts": artifacts,
            "logs": logs,
        }

    def _parse_skill_md(self, content: str) -> tuple[Dict, list[Dict]]:
        import re
        front_matter = {}
        steps = []

        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if fm_match:
            import yaml
            try:
                front_matter = yaml.safe_load(fm_match.group(1)) or {}
            except:
                pass

        step_pattern = r'## Step (\d+)\n(.*?)(?=\n## |\Z)'
        for match in re.finditer(step_pattern, content, re.DOTALL):
            step_text = match.group(2).strip()
            step = {"description": step_text}
            if '`' in step_text:
                code_match = re.search(r'`([^`]+)`', step_text)
                if code_match:
                    step["command"] = code_match.group(1)
            steps.append(step)

        return front_matter, steps

    def _load_template(self, skill_id: str, template_name: str) -> Optional[str]:
        template_path = os.path.join(
            self.skill_packs_root, skill_id, "templates", template_name
        )
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None

    def list_skills(self) -> list[Dict[str, str]]:
        skills = []
        if not os.path.exists(self.skill_packs_root):
            return skills

        for item in os.listdir(self.skill_packs_root):
            item_path = os.path.join(self.skill_packs_root, item)
            if os.path.isdir(item_path):
                skill_md = os.path.join(item_path, "skill.md")
                if os.path.exists(skill_md):
                    with open(skill_md, 'r', encoding='utf-8') as f:
                        content = f.read()
                    fm, _ = self._parse_skill_md(content)
                    skills.append({
                        "id": item,
                        "name": fm.get("skill", item),
                        "description": fm.get("description", ""),
                        "version": fm.get("version", "1.0"),
                    })
        return skills


class ClaudeSkillBackend(SkillBackend):
    """Execute skills via Claude's skill system."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_tokens = max_tokens

    @property
    def backend_name(self) -> str:
        return "claude"

    def run(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "success": False,
                "output": "Claude API key not configured",
                "artifacts": [],
                "logs": ["ERROR: ANTHROPIC_API_KEY not set"],
            }

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            system_prompt = self._build_skill_prompt(skill_id, context)
            user_message = task.get("raw", "")

            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            output = response.content[0].text if response.content else ""

            return {
                "success": True,
                "output": output,
                "artifacts": [],
                "logs": [f"Claude skill '{skill_id}' executed successfully"],
            }
        except ImportError:
            return {
                "success": False,
                "output": "anthropic package not installed",
                "artifacts": [],
                "logs": ["ERROR: pip install anthropic"],
            }
        except Exception as e:
            return {
                "success": False,
                "output": f"Claude API error: {str(e)}",
                "artifacts": [],
                "logs": [f"ERROR: {str(e)}"],
            }

    def _build_skill_prompt(self, skill_id: str, context: Dict) -> str:
        skill_config = context.get("skill_configs", {}).get(skill_id, {})
        description = skill_config.get("description", f"Execute skill: {skill_id}")
        constraints = skill_config.get("constraints", "")

        prompt = f"""You are executing a deterministic skill: {skill_id}.

Skill description: {description}
"""
        if constraints:
            prompt += f"""
Constraints:
{constraints}
"""
        prompt += """
Your response should be focused on completing the skill task.
Do not include explanatory text about being an AI.
"""
        return prompt

    def list_skills(self) -> list[Dict[str, str]]:
        return [
            {"id": "claude-code", "name": "Claude Code", "description": "General coding assistant"},
            {"id": "claude-refactor", "name": "Claude Refactor", "description": "Code refactoring"},
            {"id": "claude-review", "name": "Claude Review", "description": "Code review"},
        ]


class OpenClawSkillBackend(SkillBackend):
    """Execute skills via OpenClaw's skill system."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        cli_path: Optional[str] = None,
    ):
        self.api_url = api_url or os.getenv("OPENCLAW_API_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("OPENCLAW_API_KEY")
        self.cli_path = cli_path or os.getenv("OPENCLAW_CLI_PATH", "openclaw")

    @property
    def backend_name(self) -> str:
        return "openclaw"

    def run(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        try:
            import requests

            payload = {
                "skill": skill_id,
                "input": task.get("raw", ""),
                "context": {
                    "session_id": context.get("session_id", ""),
                    "params": task,
                },
            }

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                f"{self.api_url}/skills/execute",
                json=payload,
                headers=headers,
                timeout=60,
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "output": result.get("output", ""),
                    "artifacts": result.get("artifacts", []),
                    "logs": [f"OpenClaw skill '{skill_id}' executed"],
                }
            else:
                return {
                    "success": False,
                    "output": f"OpenClaw API error: {response.status_code}",
                    "artifacts": [],
                    "logs": [f"ERROR: {response.text}"],
                }
        except ImportError:
            return {
                "success": False,
                "output": "requests package not installed",
                "artifacts": [],
                "logs": ["ERROR: pip install requests"],
            }
        except Exception as e:
            return {
                "success": False,
                "output": f"OpenClaw execution error: {str(e)}",
                "artifacts": [],
                "logs": [f"ERROR: {str(e)}"],
            }

    def list_skills(self) -> list[Dict[str, str]]:
        try:
            import requests
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            response = requests.get(f"{self.api_url}/skills", headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get("skills", [])
        except:
            pass
        return [
            {"id": "openclaw-web", "name": "Web Scraper", "description": "Scrape web content"},
            {"id": "openclaw-data", "name": "Data Processor", "description": "Process data files"},
        ]


class HermesSkillBackend(SkillBackend):
    """Execute skills via Hermes agent system."""

    def __init__(
        self,
        agent_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.agent_url = agent_url or os.getenv("HERMES_AGENT_URL", "http://localhost:9000")
        self.api_key = api_key or os.getenv("HERMES_API_KEY")

    @property
    def backend_name(self) -> str:
        return "hermes"

    def run(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        try:
            import requests

            payload = {
                "action": "execute_skill",
                "skill_id": skill_id,
                "task": task.get("raw", ""),
                "params": task,
                "context": {
                    "session_id": context.get("session_id", ""),
                },
            }

            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["X-API-Key"] = self.api_key

            response = requests.post(
                f"{self.agent_url}/api/execute",
                json=payload,
                headers=headers,
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "output": result.get("output", ""),
                    "artifacts": result.get("artifacts", []),
                    "logs": [f"Hermes skill '{skill_id}' executed"],
                }
            else:
                return {
                    "success": False,
                    "output": f"Hermes agent error: {response.status_code}",
                    "artifacts": [],
                    "logs": [f"ERROR: {response.text}"],
                }
        except ImportError:
            return {
                "success": False,
                "output": "requests package not installed",
                "artifacts": [],
                "logs": ["ERROR: pip install requests"],
            }
        except Exception as e:
            return {
                "success": False,
                "output": f"Hermes execution error: {str(e)}",
                "artifacts": [],
                "logs": [f"ERROR: {str(e)}"],
            }

    def list_skills(self) -> list[Dict[str, str]]:
        try:
            import requests
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            response = requests.get(f"{self.agent_url}/api/skills", headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get("skills", [])
        except:
            pass
        return [
            {"id": "hermes-planner", "name": "Hermes Planner", "description": "Multi-step planning"},
            {"id": "hermes-research", "name": "Hermes Research", "description": "Research and analysis"},
        ]


_BACKENDS: Dict[str, SkillBackend] = {}


def get_backend(backend_name: str) -> SkillBackend:
    """Get or create a backend instance by name."""
    if backend_name not in _BACKENDS:
        if backend_name == "local":
            _BACKENDS[backend_name] = LocalSkillBackend()
        elif backend_name == "claude":
            _BACKENDS[backend_name] = ClaudeSkillBackend()
        elif backend_name == "openclaw":
            _BACKENDS[backend_name] = OpenClawSkillBackend()
        elif backend_name == "hermes":
            _BACKENDS[backend_name] = HermesSkillBackend()
        else:
            raise ValueError(f"Unknown backend: {backend_name}")
    return _BACKENDS[backend_name]


def register_backend(name: str, backend: SkillBackend) -> None:
    """Register a custom backend."""
    _BACKENDS[name] = backend
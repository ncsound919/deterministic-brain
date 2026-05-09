"""Skill backend adapters — unified interface for local and external skill systems."""
from __future__ import annotations
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_BUILDS_DIR = "builds"


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
        import re

        skill_path = os.path.join(self.skill_packs_root, skill_id, "skill.md")
        alt_path = os.path.join(self.skill_packs_root, skill_id, "SKILL.md")
        if not os.path.exists(skill_path) and os.path.exists(alt_path):
            skill_path = alt_path
        if not os.path.exists(skill_path):
            # Try nested path lookup
            for root, dirs, files in os.walk(self.skill_packs_root):
                for d in dirs:
                    for ext in ("skill.md", "SKILL.md"):
                        candidate = os.path.join(root, d, ext)
                        if os.path.exists(candidate) and skill_id in candidate:
                            skill_path = candidate
                            break

        if not os.path.exists(skill_path):
            return {
                "success": False,
                "output": f"Skill not found: {skill_id}",
                "artifacts": [],
                "logs": [f"ERROR: skill.md not found at {skill_path}"],
            }

        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()

        front_matter, steps = self._parse_skill_md(content)

        # If no executable ## Step blocks and no code blocks, try LLM fallback
        if not steps:
            code_blocks = re.findall(
                r"```(\w+)?\n(.*?)```", content, re.DOTALL
            )
            if code_blocks:
                artifacts = [
                    {"lang": lang or "text", "content": code.strip()}
                    for lang, code in code_blocks
                ]
                return {
                    "success": True,
                    "output": f"Skill: {skill_id} — extracted {len(artifacts)} code blocks",
                    "artifacts": artifacts,
                    "logs": [
                        f"Extracted {len(artifacts)} code blocks from skill.md",
                        *[f"  [{a['lang']}] {len(a['content'])} chars" for a in artifacts],
                    ],
                }

            return self._llm_fallback(skill_id, content, task, context)

        artifacts = []
        logs = []
        build_id = task.get("session_id", "")

        for i, step in enumerate(steps):
            logs.append(f"Executing step {i+1}: {step.get('description', 'unnamed')}")

            if step.get("template"):
                template_text = self._load_template(skill_id, step["template"])
                if template_text:
                    try:
                        tmpl = Template(template_text)
                        rendered = tmpl.render(**task)
                        output_path_raw = step.get("output", f"output/{skill_id}/step{i+1}.txt")
                        output_path = Template(output_path_raw).render(**task) if "{{" in output_path_raw else output_path_raw
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        file_write(output_path, rendered)
                        artifacts.append({"file": os.path.basename(output_path), "path": output_path, "type": "file"})
                        logs.append(f"Wrote {output_path} ({len(rendered)} chars)")
                    except Exception as e:
                        logs.append(f"Template error: {e}")
            elif step.get("command"):
                logs.append(f"Would execute: {step['command']}")

        return {
            "success": True,
            "output": f"Generated {len(artifacts)} files",
            "artifacts": artifacts,
            "logs": logs,
            "build_id": build_id,
            "preview_url": f"/preview/{build_id}",
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

            # Parse "Render template `X` with context" → template action
            tmpl_match = re.search(r'Render template `([^`]+)`', step_text)
            if tmpl_match:
                step["template"] = tmpl_match.group(1)

            # Parse "Write result to `path`" → output path
            write_match = re.search(r'Write result to `([^`]+)`', step_text)
            if write_match:
                step["output"] = write_match.group(1)

            # Parse backtick content as command (fallback)
            if not step.get("template"):
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

    def _llm_fallback(self, skill_id: str, skill_content: str, task: Dict, context: Dict) -> Dict[str, Any]:
        """When a skill has no templates or code, use LLM to generate actual code."""
        import hashlib
        import time
        import re

        llm_enabled = os.getenv("LLM_ENABLED", "").lower() == "true"
        if not llm_enabled:
            llm_enabled = bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))

        if not llm_enabled:
            return {
                "success": True,
                "output": f"Skill: {skill_id} — documentation (no code blocks, LLM off)",
                "artifacts": [{"lang": "text", "content": f"#[LLM OFF] {skill_content[:500]}...\n\nSet OPENROUTER_API_KEY to generate code."}],
                "logs": ["LLM is OFF — set OPENROUTER_API_KEY in .env to enable code generation"],
            }

        user_query = task.get("raw", task.get("task", "build something"))
        soul_context = task.get("soul_context", "")
        kb_context = ""
        if task.get("knowledge_context"):
            kb_context = "\n".join(
                f"- {k['title']}: {k['text'][:200]}"
                for k in task["knowledge_context"]
            )

        prompt = f"""You are an expert developer. Follow these instructions from the skill file:

{skill_content}

IMPORTANT CONTEXT:
- User request: {user_query}
{soul_context}
{kb_context}

Generate complete, working code. Output ONLY code blocks — no explanations outside code blocks.
Use ```language notation for each file. Include ALL files needed for the project to work.
For web projects include index.html with full HTML/CSS/JS inline.
For React projects include the component file and any needed imports.
For API projects include the main server file.

If writing HTML, include ALL styles inline in <style> tags — make it look production-ready:
- Use a modern dark theme with cyan/magenta accents
- Include proper responsive layout
- Add hover effects and transitions
- Make the code ready to open in a browser immediately
"""

        result = None
        logs = []

        try:
            from tools.llm.openrouter_client import get_client
            client = get_client()
            if client.available:
                logs.append("Using OpenRouter for code generation")
                response = client.generate_text(prompt, lane="coding", max_tokens=4096)
                result = response
            else:
                raise Exception("OpenRouter not available")
        except Exception:
            try:
                import os as _os
                ak = _os.getenv("ANTHROPIC_API_KEY", "")
                if ak:
                    import anthropic
                    cl = anthropic.Anthropic(api_key=ak)
                    resp = cl.messages.create(
                        model="claude-sonnet-4-5-20250514",
                        max_tokens=4096,
                        system=prompt,
                        messages=[{"role": "user", "content": user_query}],
                    )
                    result = resp.content[0].text if resp.content else ""
                    logs.append("Using Anthropic for code generation")
                else:
                    return {
                        "success": False,
                        "output": "No LLM API key configured",
                        "artifacts": [],
                        "logs": ["ERROR: Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY in .env"],
                    }
            except Exception as e2:
                return {
                    "success": False,
                    "output": f"LLM call failed: {str(e2)}",
                    "artifacts": [],
                    "logs": [f"ERROR: {str(e2)}"],
                }

        if not result:
            return {
                "success": False,
                "output": "LLM returned empty response",
                "artifacts": [],
                "logs": ["ERROR: Empty response from LLM"],
            }

        code_blocks = re.findall(r"```(\w*)\n(.*?)```", result, re.DOTALL)
        if not code_blocks:
            code_blocks = [("text", result)]

        build_id = hashlib.sha256((skill_id + user_query + str(time.time())).encode()).hexdigest()[:12]
        build_dir = os.path.join(_BUILDS_DIR, build_id)
        os.makedirs(build_dir, exist_ok=True)

        artifacts = []
        for lang, code in code_blocks:
            lang = lang.strip() or "txt"
            ext_map = {
                "html": "index.html", "css": "style.css", "javascript": "app.js",
                "js": "app.js", "jsx": "App.jsx", "tsx": "Component.tsx",
                "typescript": "index.ts", "ts": "index.ts",
                "python": "main.py", "py": "main.py",
                "json": "config.json", "yaml": "config.yaml",
                "dockerfile": "Dockerfile", "sh": "run.sh",
            }
            filename = ext_map.get(lang, f"output.{lang}")
            filepath = os.path.join(build_dir, filename)

            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(filepath):
                filepath = os.path.join(build_dir, f"{base}_{counter}{ext}")
                counter += 1

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(code.strip())

            artifacts.append({"lang": lang, "file": filename, "path": filepath, "preview_url": f"/preview/{build_id}/{filename}"})
            logs.append(f"Wrote {filename} ({len(code)} chars)")

        return {
            "success": True,
            "output": f"Generated {len(artifacts)} files in builds/{build_id}/",
            "artifacts": artifacts,
            "logs": logs,
            "build_id": build_id,
            "preview_url": f"/preview/{build_id}",
        }

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
            return self._fallback_to_openrouter(skill_id, task, context)

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
            return self._fallback_to_openrouter(skill_id, task, context)
        except Exception as e:
            return self._fallback_to_openrouter(skill_id, task, context)

    def _fallback_to_openrouter(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        """When Claude API isn't available, fall back to OpenRouter or local."""
        skill_packs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "skill_packs")
        local = LocalSkillBackend(skill_packs)

        skill_path = None
        for root, dirs, files in os.walk(skill_packs):
            for d in dirs:
                for ext in ("skill.md", "SKILL.md"):
                    candidate = os.path.join(root, d, ext)
                    if os.path.exists(candidate) and skill_id in candidate:
                        skill_path = candidate
                        break
                if skill_path:
                    break
            if skill_path:
                break

        if skill_path and os.path.exists(skill_path):
            with open(skill_path, "r", encoding="utf-8") as f:
                content = f.read()
            return local._llm_fallback(skill_id, content, task, context)
        return local.run(skill_id, task, context)

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
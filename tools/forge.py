"""forge.py — replaces repoforge as a lean Python diff + skill-pack manager.
No Tauri, no Electron. Runs as a CLI tool or is called by the API server.
"""
from __future__ import annotations
import difflib
import glob
import os
import yaml
from typing import Dict, List


class Forge:
    """
    Skill-pack manager and diff viewer:
      list_skills()              → all indexed skill.md files
      diff(old, new)             → unified diff string
      install_pack(src_dir)      → copy skill pack into skill_packs/
      validate_skill(path)       → check frontmatter against schema
      preview_output(file_path)  → read generated file for UI display
    """

    SKILLS_ROOT = "skill_packs"
    SCHEMA_PATH = "schemas/skill.schema.yaml"

    def list_skills(self) -> List[Dict]:
        skills = []
        seen = set()
        # Search both skill_packs/ and skills/ directories
        for root in [self.SKILLS_ROOT, "skills"]:
            if not os.path.isdir(root):
                continue
            for pattern in ["**/*.skill.md", "**/SKILL.md", "**/skill.md"]:
                for path in glob.glob(os.path.join(root, pattern), recursive=True):
                    if path in seen:
                        continue
                    seen.add(path)
                    try:
                        with open(path, encoding="utf-8") as f:
                            content = f.read()
                        fm = content.split("---")[1] if content.startswith("---") else ""
                        meta = yaml.safe_load(fm) or {}

                        # Extract skill ID from directory name
                        skill_id = os.path.basename(os.path.dirname(path))

                        # Determine category from parent directory structure
                        parts = path.replace("\\", "/").split("/")
                        category = parts[-3] if len(parts) >= 3 else ""

                        description = meta.get("description", meta.get("help", ""))
                        inputs = meta.get("inputs", {})
                        tools = meta.get("tools", [])
                        requires = meta.get("requires", {})

                        skills.append({
                            "skill_id":   skill_id,
                            "skill":      meta.get("skill", meta.get("name", skill_id)),
                            "description": description,
                            "version":    meta.get("version", "1.0"),
                            "category":   category if category != root.replace("/", "").replace("\\", "") else "",
                            "backend":    meta.get("backend", "local"),
                            "path":       path,
                            "inputs":     inputs if isinstance(inputs, dict) else {},
                            "tools":      tools if isinstance(tools, list) else [],
                            "requires":   {
                                "env": requires.get("env", []) if isinstance(requires, dict) else [],
                                "bins": requires.get("bins", []) if isinstance(requires, dict) else [],
                            },
                            "source_format": "external" if path.endswith("SKILL.md") else "native",
                            "monte_carlo": meta.get("monte_carlo", False),
                        })
                    except Exception:
                        pass
        return skills

    def diff(self, old_content: str, new_content: str, filename: str = "file") -> str:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        return "".join(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        ))

    def install_pack(self, src_dir: str, pack_name: str) -> Dict:
        dest = os.path.join(self.SKILLS_ROOT, pack_name)
        if not os.path.isdir(src_dir):
            return {"error": f"Source not found: {src_dir}"}
        import shutil
        shutil.copytree(src_dir, dest, dirs_exist_ok=True)
        skills = self.list_skills()
        return {"installed": dest, "total_skills": len(skills)}

    def validate_skill(self, skill_path: str) -> Dict:
        errors = []
        try:
            with open(skill_path) as f:
                content = f.read()
            if not content.startswith("---"):
                return {"valid": False, "errors": ["Missing YAML frontmatter"]}
            fm   = content.split("---")[1]
            meta = yaml.safe_load(fm) or {}
            for field in ["skill", "version", "inputs", "tools", "audit"]:
                if field not in meta:
                    errors.append(f"Missing required field: '{field}'")
            if meta.get("monte_carlo") and "choices" not in meta:
                errors.append("monte_carlo=true but no 'choices' defined")
        except Exception as exc:
            errors.append(str(exc))
        return {"valid": len(errors) == 0, "errors": errors, "path": skill_path}

    def preview_output(self, file_path: str) -> Dict:
        if not os.path.exists(file_path):
            return {"error": f"Not found: {file_path}"}
        with open(file_path) as f:
            return {"content": f.read(), "path": file_path}


# ── singleton for tool registry ──────────────────────────────────────────────
_forge = Forge()


def forge_list_skills() -> Dict:
    return {"skills": _forge.list_skills()}


def forge_validate(skill_path: str) -> Dict:
    return _forge.validate_skill(skill_path)


def forge_diff(old: str, new: str, filename: str = "file") -> Dict:
    return {"diff": _forge.diff(old, new, filename)}

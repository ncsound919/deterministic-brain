"""Template builder — upload .md/.yaml/.json, extract `{{variables}}`, ask questions,
generate full project builds from answers.

Integration points:
- Soul: uses preferences (languages, frameworks, naming) as defaults
- Knowledge Bank: stores generated templates as fragments
- DCA Engine: feeds generated code into the build pipeline
"""
from __future__ import annotations
import re
import os
import json
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TemplateQuestion:
    key: str
    label: str
    default: str = ""
    example: str = ""
    required: bool = False
    answered: str = ""

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "default": self.default,
            "example": self.example,
            "required": self.required,
            "answered": self.answered or self.default,
        }


@dataclass
class ProjectTemplate:
    id: str = ""
    name: str = ""
    source_path: str = ""
    raw_content: str = ""
    questions: List[TemplateQuestion] = field(default_factory=list)
    answered: bool = False
    generated: str = ""
    ts_created: float = field(default_factory=time.time)

    def extract_questions(self) -> List[TemplateQuestion]:
        pattern = r'\{\{(.+?)\}\}'
        matches = re.findall(pattern, self.raw_content)
        seen = set()
        questions = []
        for m in matches:
            key = m.strip()
            if key in seen:
                continue
            seen.add(key)
            label, default, example = _parse_template_var(key)
            questions.append(TemplateQuestion(
                key=key,
                label=label,
                default=default,
                example=example,
                required=True,
            ))
        self.questions = questions
        return questions

    def apply_answers(self, answers: Dict[str, str]) -> str:
        result = self.raw_content
        for q in self.questions:
            val = answers.get(q.key, q.answered or q.default)
            result = result.replace("{{" + q.key + "}}", val)
            result = result.replace("{{ " + q.key + " }}", val)
        self.generated = result
        self.answered = True
        return result

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_path": self.source_path,
            "questions": [q.to_dict() for q in self.questions],
            "answered": self.answered,
            "ts_created": self.ts_created,
        }


def _parse_template_var(key: str) -> Tuple[str, str, str]:
    label = key.replace("_", " ").replace("-", " ").title()
    default = ""
    example = ""

    hint_match = re.match(r'(.+?)\s*\?\s*"?(.+?)"?$', key)
    if hint_match:
        key = hint_match.group(1).strip()
        label = key.replace("_", " ").title()
        hint = hint_match.group(2)
        if "|" in hint:
            parts = hint.split("|")
            default = parts[0].strip()
            example = parts[1].strip() if len(parts) > 1 else ""
        else:
            default = hint.strip()

    return label, default, example


class TemplateBuilder:
    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        os.makedirs(templates_dir, exist_ok=True)
        self._templates: Dict[str, ProjectTemplate] = {}
        self._load_saved()

    def _load_saved(self):
        idx_path = os.path.join(self.templates_dir, "index.json")
        if os.path.exists(idx_path):
            try:
                with open(idx_path) as f:
                    data = json.load(f)
                for item in data:
                    tmpl_path = os.path.join(self.templates_dir, item["id"] + ".json")
                    if os.path.exists(tmpl_path):
                        with open(tmpl_path) as f:
                            d = json.load(f)
                        t = ProjectTemplate(
                            id=d["id"], name=d["name"], source_path=d.get("source_path", ""),
                            raw_content=d.get("raw_content", ""), answered=d.get("answered", False),
                            generated=d.get("generated", ""), ts_created=d.get("ts_created", time.time()),
                        )
                        t.questions = [TemplateQuestion(**q) for q in d.get("questions", [])]
                        self._templates[t.id] = t
            except Exception:
                pass

    def _save_index(self):
        idx_path = os.path.join(self.templates_dir, "index.json")
        items = [{"id": t.id, "name": t.name, "ts_created": t.ts_created}
                 for t in self._templates.values()]
        with open(idx_path, "w") as f:
            json.dump(items, f, indent=2)

    def _save_template(self, t: ProjectTemplate):
        path = os.path.join(self.templates_dir, t.id + ".json")
        d = {
            "id": t.id, "name": t.name, "source_path": t.source_path,
            "raw_content": t.raw_content, "answered": t.answered,
            "generated": t.generated, "ts_created": t.ts_created,
            "questions": [q.to_dict() for q in t.questions],
        }
        with open(path, "w") as f:
            json.dump(d, f, indent=2)

    def upload_text(self, name: str, content: str) -> ProjectTemplate:
        tid = hashlib.sha256((name + content).encode()).hexdigest()[:16]
        if tid in self._templates:
            return self._templates[tid]
        t = ProjectTemplate(
            id=tid, name=name, source_path=f"upload://{name.replace(' ', '-')}",
            raw_content=content,
        )
        t.extract_questions()
        self._templates[tid] = t
        self._save_template(t)
        self._save_index()
        return t

    def upload_file(self, filepath: str) -> Optional[ProjectTemplate]:
        ext = os.path.splitext(filepath)[1].lower()
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None
        name = os.path.basename(filepath)
        tid = hashlib.sha256(content.encode()).hexdigest()[:16]
        if tid in self._templates:
            return self._templates[tid]
        t = ProjectTemplate(
            id=tid, name=name, source_path=filepath, raw_content=content,
        )
        t.extract_questions()
        self._templates[tid] = t
        self._save_template(t)
        self._save_index()
        return t

    def get(self, template_id: str) -> Optional[ProjectTemplate]:
        return self._templates.get(template_id)

    def list_all(self) -> List[ProjectTemplate]:
        return list(self._templates.values())

    def answer(self, template_id: str, answers: Dict[str, str]) -> Optional[str]:
        t = self._templates.get(template_id)
        if not t:
            return None
        result = t.apply_answers(answers)
        self._save_template(t)
        return result

    def delete(self, template_id: str) -> bool:
        if template_id not in self._templates:
            return False
        del self._templates[template_id]
        path = os.path.join(self.templates_dir, template_id + ".json")
        if os.path.exists(path):
            os.remove(path)
        self._save_index()
        return True

    def boil(self, template_id: str, answers: Dict[str, str],
             soul_context: str = "") -> Dict[str, Any]:
        """Generate a full build task from template + answers + soul context.

        Returns a dict ready to feed into /task or swarm dispatch.
        """
        t = self._templates.get(template_id)
        if not t:
            return {"error": "template not found"}
        generated = t.apply_answers(answers)
        self._save_template(t)

        task = {
            "query": f"build:project from template {t.name}",
            "template_id": template_id,
            "template_name": t.name,
            "generated_content": generated,
            "soul_context": soul_context,
            "answers": answers,
            "artifacts": [_classify_output(generated)],
        }
        return task


def _classify_output(content: str) -> Dict:
    artifacts = []
    if "<html" in content.lower() or "<!doctype" in content.lower():
        artifacts.append({"lang": "html", "filename": "index.html"})
    if "import react" in content.lower() or "export default" in content.lower():
        artifacts.append({"lang": "typescript", "filename": "component.tsx"})
    if "def " in content and "import " in content:
        artifacts.append({"lang": "python", "filename": "main.py"})
    if "docker" in content.lower() or "FROM " in content:
        artifacts.append({"lang": "dockerfile", "filename": "Dockerfile"})
    if "apiVersion" in content or "kind:" in content:
        artifacts.append({"lang": "yaml", "filename": "deploy.yaml"})
    if not artifacts:
        artifacts.append({"lang": "text", "filename": "output.txt"})
    return artifacts[0]


_BUILDER: Optional[TemplateBuilder] = None


def get_template_builder() -> TemplateBuilder:
    global _BUILDER
    if _BUILDER is None:
        _BUILDER = TemplateBuilder()
    return _BUILDER

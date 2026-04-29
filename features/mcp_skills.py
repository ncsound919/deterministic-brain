from __future__ import annotations
"""
MCP_SKILLS — Skills from MCP servers.

Loads reusable prompt-template skills from a .skills/ directory and
registers them as callable brain tools. Skills are YAML/JSON files with
a name, description, system prompt, and parameter schema.

Skills can be invoked via:
  brain.run('/skill:<skill_name> <args>')
or directly:
  mcp_skills.invoke('skill_name', params)
"""
import json
import os
from pathlib import Path
from typing import Any

_SKILLS_DIR = Path(os.getenv('SKILLS_DIR', '.skills'))
_SKILLS_DIR.mkdir(exist_ok=True)
_REGISTRY: dict[str, dict] = {}


def _load_all() -> None:
    for p in _SKILLS_DIR.glob('*.json'):
        try:
            skill = json.loads(p.read_text())
            _REGISTRY[skill['name']] = skill
        except Exception:
            pass


_load_all()


def register(name: str, description: str, system: str,
             params: dict | None = None, lane: str = 'cross_domain') -> dict:
    skill = {
        'name': name,
        'description': description,
        'system': system,
        'params': params or {},
        'lane': lane,
    }
    _REGISTRY[name] = skill
    (_SKILLS_DIR / f'{name}.json').write_text(json.dumps(skill, indent=2))
    return skill


def invoke(name: str, params: dict | None = None, query: str = '') -> dict:
    skill = _REGISTRY.get(name)
    if not skill:
        return {'error': f'Skill "{name}" not found. Available: {list(_REGISTRY.keys())}'}
    from tools.llm.router import chat
    user_msg = query or str(params or {})
    output = chat(system=skill['system'], user=user_msg, lane=skill.get('lane', 'cross_domain'))
    return {'skill': name, 'output': output, 'params': params}


def list_skills() -> list[dict]:
    return [
        {'name': s['name'], 'description': s['description'], 'lane': s.get('lane', 'cross_domain')}
        for s in _REGISTRY.values()
    ]

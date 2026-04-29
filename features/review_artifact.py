from __future__ import annotations
"""
REVIEW_ARTIFACT — Review artifact tool.

Submits any artifact (code, plan, document) for structured multi-pass review:
1. Correctness   — Is it factually/logically correct?
2. Completeness  — Are edge cases/requirements covered?
3. Quality       — Style, clarity, best practices
4. Security      — Vulnerabilities, data exposure
5. Verdict       — APPROVE | REQUEST_CHANGES | REJECT + overall score
"""
import json
from tools.llm.router import chat

_SYSTEM = """You are a senior technical reviewer.
Review the given artifact and return structured JSON:
{
  "correctness":   {"score": 1-10, "issues": [str], "passed": bool},
  "completeness":  {"score": 1-10, "missing": [str], "passed": bool},
  "quality":       {"score": 1-10, "suggestions": [str], "passed": bool},
  "security":      {"score": 1-10, "vulnerabilities": [str], "passed": bool},
  "verdict":       "APPROVE|REQUEST_CHANGES|REJECT",
  "overall_score": 1-10,
  "summary":       str
}"""


def review(artifact: str, artifact_type: str = 'code', context: str = '') -> dict:
    user_msg = (
        f'Artifact type: {artifact_type}\n'
        + (f'Context: {context}\n\n' if context else '')
        + f'Artifact:\n{artifact[:3000]}'
    )
    raw = chat(system=_SYSTEM, user=user_msg, lane='coding' if artifact_type == 'code' else 'cross_domain',
               max_tokens=1500)
    try:
        clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        return json.loads(clean)
    except Exception:
        return {
            'verdict': 'REQUEST_CHANGES',
            'overall_score': 5,
            'summary': raw[:500],
            'correctness': {'score': 5, 'issues': [], 'passed': True},
            'completeness': {'score': 5, 'missing': [], 'passed': True},
            'quality': {'score': 5, 'suggestions': [], 'passed': True},
            'security': {'score': 5, 'vulnerabilities': [], 'passed': True},
        }

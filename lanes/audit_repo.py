"""Lane: audit-repo — walk files, run linters, score, emit report."""
from __future__ import annotations
import os
from typing import Dict

from reasoning.auditor import DeterministicAuditor
from planners.scorer import DeterministicScorer
from tools.tracing import log_event

_AUDITABLE_EXTS = {".py", ".ts", ".tsx", ".js"}


def run(inputs: Dict) -> Dict:
    repo_path = inputs.get("repo_path", ".")
    if not os.path.isdir(repo_path):
        return {"error": f"Directory not found: {repo_path}"}

    auditor = DeterministicAuditor()
    scorer  = DeterministicScorer()
    report  = []

    for root, _, files in os.walk(repo_path):
        # skip hidden / node_modules / .venv
        if any(p.startswith(".") or p in {"node_modules", ".venv", "__pycache__"}
               for p in root.split(os.sep)):
            continue
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _AUDITABLE_EXTS:
                continue
            fpath = os.path.join(root, fname)
            passed = auditor.run_audit([f"run_linter {fpath}"], {"output_file": fpath})
            score  = scorer.score({"success": passed, "output": fpath})
            report.append({"file": fpath, "passed": passed, "score": score})

    total   = len(report)
    passing = sum(1 for r in report if r["passed"])
    avg     = round(sum(r["score"] for r in report) / total, 2) if total else 0

    summary = {"total_files": total, "passing": passing, "avg_score": avg, "files": report}
    log_event("audit_repo", {"repo_path": repo_path, **summary})
    return {"success": True, **summary}

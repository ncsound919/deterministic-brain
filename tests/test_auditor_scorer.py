"""Tests for reasoning/auditor.py and planners/scorer.py."""
import json
import os
from pathlib import Path

import pytest


class TestDeterministicAuditor:
    def test_auditor_imports(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        assert auditor is not None

    def test_run_audit_with_context(self):
        from reasoning.auditor import DeterministicAuditor
        import sys
        auditor = DeterministicAuditor()
        if sys.platform == "win32":
            # cmd /c exit 0 — works on Windows without path quoting issues
            commands = ["cmd /c exit 0"]
        else:
            commands = ["true"]
        result = auditor.run_audit(commands, {})
        assert result is True

    def test_run_audit_failing_command(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        # Use a non-existent binary — guaranteed to fail
        result = auditor.run_audit(["nonexistent_cmd_12345"], {})
        assert result is False

    def test_run_audit_no_commands(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        result = auditor.run_audit([], {})
        assert result is True

    def test_score_success(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        assert auditor.score({"success": True}) == 1

    def test_score_failure(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        assert auditor.score({"success": False}) == 0

    def test_score_truthy(self):
        from reasoning.auditor import DeterministicAuditor
        auditor = DeterministicAuditor()
        assert auditor.score({"success": 1}) == 1


class TestDeterministicScorer:
    def test_scorer_imports(self):
        from planners.scorer import DeterministicScorer
        scorer = DeterministicScorer()
        assert scorer is not None

    def test_all_pass_scores_high(self):
        from planners.scorer import DeterministicScorer
        scorer = DeterministicScorer()
        result = {
            "success": True,
            "files": [],
        }
        score = scorer.score(result)
        # audit_pass = 50, complexity = 0.5 fallback, coverage = 0.0 fallback, line_count = 0.5 fallback
        # = 50 + 10 + 0 + 5 = 65
        assert score == pytest.approx(65.0, rel=0.1)

    def test_audit_fail_scores_low(self):
        from planners.scorer import DeterministicScorer
        scorer = DeterministicScorer()
        result = {
            "success": False,
            "files": [],
        }
        score = scorer.score(result)
        # audit_pass = 0, complexity = 0.5, coverage = 0.0, line_count = 0.5
        # = 0 + 10 + 0 + 5 = 15
        assert score == pytest.approx(15.0, rel=0.1)

    def test_weights_sum_to_100(self):
        from planners.scorer import DeterministicScorer
        assert sum(DeterministicScorer.WEIGHTS.values()) == 100

    def test_score_with_file(self, tmp_path):
        from planners.scorer import DeterministicScorer
        # Create a small test file
        p = tmp_path / "test.py"
        p.write_text("print('hello')\n")
        scorer = DeterministicScorer()
        result = {
            "success": True,
            "files": [str(p)],
        }
        score = scorer.score(result)
        assert score > 0


class TestPreAuditCheck:
    def test_check_clean_text(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("hello world")
        assert result.audit_ok is True

    def test_check_with_dollar_paren(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("$(whoami)")
        assert result.audit_ok is False
        assert "injection" in result.blocked_reason.lower()

    def test_check_with_backtick_command(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("`cat /etc/passwd`")
        assert result.audit_ok is False

    def test_check_with_path_traversal(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("../../etc/passwd")
        assert result.audit_ok is False

    def test_check_with_url_encoded_dollar(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("test%24(whoami)")
        assert result.audit_ok is False

    def test_check_with_newline(self):
        from reasoning.math_engine import PreAudit
        pa = PreAudit()
        result = pa.check("hello\nrm -rf /")
        assert result.audit_ok is False

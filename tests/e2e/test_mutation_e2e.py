"""Mutation Testing for E2E Test Validation.

Runs mutation testing to prove tests aren't fluff.
If mutants survive, tests have real holes.
"""
from __future__ import annotations
import os
import subprocess
import pytest


class TestMutationCoverage:
    """Test that mutations are caught by E2E tests."""

    @pytest.mark.mutation
    @pytest.mark.skipif(
        os.environ.get("RUN_MUTATION_TESTS") != "1",
        reason="Mutation testing requires RUN_MUTATION_TESTS=1"
    )
    def test_router_logic_mutation_caught(self):
        """If router condition flips, routing tests should fail."""
        try:
            result = subprocess.run(
                ["mutmut", "run", "--", "tests/test_routing_e2e.py"],
                capture_output=True,
                timeout=300,
            )
            output = result.stdout + result.stderr
            
            assert "survived" not in output.lower() or result.returncode == 0
        except FileNotFoundError:
            pytest.skip("mutmut not installed")

    @pytest.mark.mutation
    @pytest.mark.skipif(
        os.environ.get("RUN_MUTATION_TESTS") != "1",
        reason="Mutation testing requires RUN_MUTATION_TESTS=1"
    )
    def test_skill_execution_mutation_caught(self):
        """If skill dispatcher breaks, skill tests should fail."""
        try:
            result = subprocess.run(
                ["mutmut", "run", "--", "tests/test_skills_e2e.py"],
                capture_output=True,
                timeout=300,
            )
            assert result.returncode == 0 or "survived" not in result.stdout.lower()
        except FileNotFoundError:
            pytest.skip("mutmut not installed")

    @pytest.mark.mutation
    @pytest.mark.skipif(
        os.environ.get("RUN_MUTATION_TESTS") != "1",
        reason="Mutation testing requires RUN_MUTATION_TESTS=1"
    )
    def test_scheduler_mutation_caught(self):
        """If scheduler breaks, scheduler tests should fail."""
        try:
            result = subprocess.run(
                ["mutmut", "run", "--", "tests/test_scheduler_e2e.py"],
                capture_output=True,
                timeout=300,
            )
            assert result.returncode == 0
        except FileNotFoundError:
            pytest.skip("mutmut not installed")

    @pytest.mark.mutation
    @pytest.mark.skipif(
        os.environ.get("RUN_MUTATION_TESTS") != "1",
        reason="Mutation testing requires RUN_MUTATION_TESTS=1"
    )
    def test_determinism_mutation_caught(self):
        """If deterministic seed is removed, determinism tests should fail."""
        try:
            result = subprocess.run(
                ["mutmut", "run", "--", "tests/test_determinism_e2e.py"],
                capture_output=True,
                timeout=300,
            )
            assert result.returncode == 0
        except FileNotFoundError:
            pytest.skip("mutmut not installed")


class TestMutationManual:
    """Manual mutation testing commands for local use."""

    def test_mutmut_available(self):
        """Check if mutmut is available."""
        try:
            result = subprocess.run(
                ["mutmut", "--version"],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0
        except FileNotFoundError:
            pytest.skip("mutmut not installed")

    def test_cosmic_ray_available(self):
        """Check if cosmic-ray is available."""
        try:
            result = subprocess.run(
                ["cr", "--version"],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0
        except FileNotFoundError:
            pytest.skip("cosmic-ray not installed")


MUTATION_COMMANDS = """
# To run mutation testing locally:
# 1. Install: pip install mutmut
# 2. Run: RUN_MUTATION_TESTS=1 pytest tests/e2e/test_mutation_e2e.py -v

# Or run manually:
mutmut run -- tests/test_routing_e2e.py
mutmut run -- tests/test_skills_e2e.py  
mutmut run -- tests/test_scheduler_e2e.py
mutmut run -- tests/test_determinism_e2e.py

# View results:
mutmut results

# Key mutations to verify:
# - Flip routing condition (if task.type == "REST") -> test should fail
# - Remove scheduler persistence -> test should fail
# - Replace seed with random -> determinism tests should fail
"""
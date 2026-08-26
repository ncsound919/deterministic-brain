"""Shared test configuration.

Forces the LLM router's deterministic stub path so unit/e2e suites never
depend on a running local model server or live inference speed. Individual
tests that exercise real backends can override with monkeypatch.setenv.
"""
import os

os.environ.setdefault("BRAIN_DISABLE_LLM", "1")

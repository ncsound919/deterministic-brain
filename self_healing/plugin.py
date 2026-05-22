"""Self-Healing Pytest Plugin for E2E Tests.

Integration point for pytest to automatically heal test failures.
"""
from __future__ import annotations
import logging
import pytest
from typing import Optional

from self_healing.healer import Healer, create_healer
from self_healing.fuzzy_matcher import create_fuzzy_matcher
from self_healing.state_replayer import create_state_replayer
from self_healing.pattern_healer import create_pattern_healer, create_comparator
from self_healing.golden_manager import create_golden_manager, GoldenManager

logger = logging.getLogger(__name__)


class SelfHealingPlugin:
    """Pytest plugin for automatic test healing."""

    def __init__(self):
        self._healers: dict[str, Healer] = {}
        self._golden_manager: Optional[GoldenManager] = None
        self._fuzzy_matcher = None
        self._state_replayer = None
        self._pattern_healer = None
        self._heals_applied: list = []

    @pytest.hookimpl
    def pytest_runtest_makereport(self, item, call):
        """Hook to capture test failures and attempt healing."""
        if call.when != "call":
            return
        
        if call.excinfo is None:
            self._on_test_success(item)
            return
        
        self._on_test_failure(item, call.excinfo)

    def _on_test_success(self, item) -> None:
        """Handle test success."""
        test_id = item.name
        if self._golden_manager:
            self._golden_manager.record_success(test_id)

    def _on_test_failure(self, item, excinfo) -> None:
        """Handle test failure and attempt healing."""
        test_id = item.name
        
        if self._golden_manager:
            self._golden_manager.record_failure(test_id)
        
        healer = self._get_healer(test_id)
        
        error = excinfo.value
        expected = getattr(item, "_pytest_expected", None)
        actual = str(error)
        
        input_data = self._extract_input(item)
        
        healer.capture_artifacts(
            test_id=test_id,
            error=error,
            expected=expected,
            actual=actual,
            input_data=input_data,
        )
        
        failure_type = healer.diagnose()
        
        if failure_type and failure_type != "UNKNOWN":
            repair_record = healer.repair(failure_type)
            
            if repair_record:
                self._heals_applied.append({
                    "test_id": test_id,
                    "failure_type": failure_type.value,
                    "repair": repair_record.repair_applied,
                })
                
                logger.info(f"Healed {test_id}: {failure_type.value}")

    def _get_healer(self, test_id: str) -> Healer:
        """Get or create healer for test."""
        if test_id not in self._healers:
            self._healers[test_id] = create_healer(test_id)
        return self._healers[test_id]

    def _extract_input(self, item) -> dict:
        """Extract input data from test item."""
        input_data = {}
        
        if hasattr(item, "funcargs"):
            for key, value in item.funcargs.items():
                if isinstance(value, str):
                    input_data[key] = value
                elif isinstance(value, dict):
                    input_data[key] = value
        
        return input_data

    @pytest.hookimpl
    def pytest_sessionfinish(self, session, exitstatus):
        """Print healing summary at end of session."""
        if not self._heals_applied:
            return
        
        total = len(self._heals_applied)
        logger.info(f"\n🩹 Self-healing applied {total} fixes:")
        
        for heal in self._heals_applied:
            logger.info(f"   - {heal['test_id']}: {heal['failure_type']} -> {heal['repair'][:50]}")
        
        if self._golden_manager:
            stats = self._golden_manager.get_statistics()
            logger.info(f"\n📊 Golden data stats: {stats}")

    def pytest_terminal_summary(self, terminalreporter, exitstatus, config):
        """Add healing summary to test report."""
        if self._heals_applied:
            terminalreporter.write_sep("=", "Self-Healing Summary")
            terminalreporter.write_line(f"Applied {len(self._heals_applied)} automatic fixes")


def pytest_configure(config):
    """Configure pytest with self-healing plugin."""
    plugin = SelfHealingPlugin()
    config.pluginmanager.register(plugin, "self-healing")
    
    config.addinivalue_line(
        "markers", "self_heal: mark test as self-healing enabled"
    )


@pytest.fixture
def healer():
    """Fixture providing a healer instance."""
    return create_healer("test")


@pytest.fixture
def fuzzy_matcher():
    """Fixture providing fuzzy matcher."""
    return create_fuzzy_matcher()


@pytest.fixture
def state_replayer():
    """Fixture providing state replayer."""
    return create_state_replayer()


@pytest.fixture
def pattern_healer():
    """Fixture providing pattern healer."""
    return create_pattern_healer()


@pytest.fixture
def golden_manager():
    """Fixture providing golden manager."""
    return create_golden_manager()


@pytest.fixture
def response_comparator():
    """Fixture providing response comparator."""
    return create_comparator()
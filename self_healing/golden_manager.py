"""Golden Data Manager for E2E Test Regression.

Manages golden data for deterministic comparison and auto-regeneration.
"""
from __future__ import annotations
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

GOLDEN_DIR = Path(__file__).parent.parent / "tests" / "e2e" / "golden"
AUTO_HEAL_DIR = Path.home() / ".deterministic-brain" / "healer_cache" / "auto_healed"


@dataclass
class GoldenRecord:
    """A golden data record."""
    test_id: str
    input_hash: str
    expected: Any
    created_at: str
    auto_regenerated: bool = False
    notes: str = ""


@dataclass
class RegenerationPolicy:
    """Policy for golden data regeneration."""
    consecutive_failures_threshold: int = 3
    confidence_threshold: float = 0.9
    max_regenerations_per_test: int = 5
    require_manual_review: bool = True


class GoldenManager:
    """Manages golden data for E2E tests."""

    def __init__(self, policy: Optional[RegenerationPolicy] = None):
        self.policy = policy or RegenerationPolicy()
        self._records: Dict[str, GoldenRecord] = {}
        self._failure_counts: Dict[str, int] = {}
        self._regeneration_counts: Dict[str, int] = {}
        self._load_golden_data()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure golden data directories exist."""
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        AUTO_HEAL_DIR.mkdir(parents=True, exist_ok=True)

    def _load_golden_data(self) -> None:
        """Load golden data from disk."""
        golden_file = GOLDEN_DIR / "golden_data.json"
        
        if golden_file.exists():
            try:
                with open(golden_file) as f:
                    data = json.load(f)
                    for test_id, record_data in data.items():
                        self._records[test_id] = GoldenRecord(**record_data)
            except Exception as e:
                logger.warning(f"Failed to load golden data: {e}")

    def _save_golden_data(self) -> None:
        """Save golden data to disk."""
        golden_file = GOLDEN_DIR / "golden_data.json"
        
        data = {
            test_id: record.__dict__
            for test_id, record in self._records.items()
        }
        
        with open(golden_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_golden(self, test_id: str, input_data: Any) -> Optional[Any]:
        """Get golden expected value for test.
        
        Args:
            test_id: Test identifier
            input_data: Input that was given
        
        Returns:
            Golden expected value or None
        """
        input_hash = self._hash_input(input_data)
        key = f"{test_id}:{input_hash}"
        
        if key in self._records:
            return self._records[key].expected
        
        if test_id in self._records:
            return self._records[test_id].expected
        
        return None

    def _hash_input(self, input_data: Any) -> str:
        """Hash input data."""
        data_str = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]

    def record_failure(self, test_id: str) -> None:
        """Record a test failure for tracking."""
        self._failure_counts[test_id] = self._failure_counts.get(test_id, 0) + 1

    def record_success(self, test_id: str) -> None:
        """Record a test success, reset failure count."""
        self._failure_counts[test_id] = 0

    def should_regenerate(self, test_id: str, confidence: float = 1.0) -> bool:
        """Determine if golden data should be regenerated.
        
        Args:
            test_id: Test identifier  
            confidence: Confidence score from test
        
        Returns:
            True if regeneration should occur
        """
        if confidence < self.policy.confidence_threshold:
            return False
        
        failures = self._failure_counts.get(test_id, 0)
        if failures < self.policy.consecutive_failures_threshold:
            return False
        
        regens = self._regeneration_counts.get(test_id, 0)
        if regens >= self.policy.max_regenerations_per_test:
            logger.warning(f"Max regenerations reached for {test_id}")
            return False
        
        return True

    def regenerate_golden(self, test_id: str, new_expected: Any, 
                        input_data: Any, notes: str = "") -> bool:
        """Regenerate golden data.
        
        Args:
            test_id: Test identifier
            new_expected: New expected value
            input_data: Input that was given
            notes: Notes about regeneration
        
        Returns:
            True if regenerated successfully
        """
        input_hash = self._hash_input(input_data)
        
        record = GoldenRecord(
            test_id=test_id,
            input_hash=input_hash,
            expected=new_expected,
            created_at=datetime.utcnow().isoformat(),
            auto_regenerated=True,
            notes=notes or f"Auto-regenerated after {self._failure_counts.get(test_id, 0)} failures"
        )
        
        key = f"{test_id}:{input_hash}"
        self._records[key] = record
        
        self._regeneration_counts[test_id] = self._regeneration_counts.get(test_id, 0) + 1
        self._failure_counts[test_id] = 0
        
        self._save_golden_data()
        self._save_auto_healed_record(test_id, record)
        
        logger.info(f"Regenerated golden data for {test_id}")
        return True

    def _save_auto_healed_record(self, test_id: str, record: GoldenRecord) -> None:
        """Save auto-healed record for audit."""
        auto_file = AUTO_HEAL_DIR / f"{test_id}_auto_healed.json"
        
        with open(auto_file, "w") as f:
            json.dump(record.__dict__, f, indent=2)

    def get_regeneration_candidates(self) -> List[Dict[str, Any]]:
        """Get tests that need regeneration review.
        
        Returns:
            List of test info that needs manual review
        """
        candidates = []
        
        for test_id, failures in self._failure_counts.items():
            if failures >= self.policy.consecutive_failures_threshold:
                candidates.append({
                    "test_id": test_id,
                    "consecutive_failures": failures,
                    "regeneration_count": self._regeneration_counts.get(test_id, 0)
                })
        
        return candidates

    def get_statistics(self) -> Dict[str, Any]:
        """Get golden data statistics."""
        return {
            "total_golden_records": len(self._records),
            "tests_with_failures": len(self._failure_counts),
            "tests_with_regenerations": len(self._regeneration_counts),
            "candidates_for_review": len(self.get_regeneration_candidates()),
        }

    def add_golden(self, test_id: str, expected: Any, input_data: Any = None) -> None:
        """Add new golden data record.
        
        Args:
            test_id: Test identifier
            expected: Expected value
            input_data: Optional input for hashing
        """
        input_hash = self._hash_input(input_data) if input_data else "default"
        
        record = GoldenRecord(
            test_id=test_id,
            input_hash=input_hash,
            expected=expected,
            created_at=datetime.utcnow().isoformat(),
        )
        
        key = f"{test_id}:{input_hash}"
        self._records[key] = record
        
        self._save_golden_data()


def create_golden_manager(policy: Optional[RegenerationPolicy] = None) -> GoldenManager:
    """Create a golden manager."""
    return GoldenManager(policy)
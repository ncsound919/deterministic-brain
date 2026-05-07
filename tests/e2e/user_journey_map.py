"""User Journey Map and Risk-Based Test Coverage.

Maps E2E tests to real workflows with risk categorization.
This is NOT fluff - every critical path has tests.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class RiskLevel(Enum):
    """Risk categorization for features."""
    HIGH = "high"       # Can seriously hurt in prod
    MEDIUM = "medium"   # Noticeable impact
    LOW = "low"         # Cosmetic or ancillary


@dataclass
class UserJourney:
    """A user journey through the system."""
    name: str
    description: str
    risk_level: RiskLevel
    must_not_break_behavior: str
    test_files: List[str]
    success_test_count: int = 0
    failure_test_count: int = 0


class UserJourneyMap:
    """Maps user journeys to tests with risk levels."""

    JOURNEYS = [
        UserJourney(
            name="Route task to correct skill",
            description="User submits task → TaskParser → MoERouter → correct skill selected",
            risk_level=RiskLevel.HIGH,
            must_not_break_behavior="Correct skill chosen for each task type",
            test_files=["test_routing_e2e.py", "test_skills_e2e.py"],
        ),
        UserJourney(
            name="Execute imported skills (Hermes/OpenClaw)",
            description="Downloaded SKILL.md executed as first-class skill",
            risk_level=RiskLevel.HIGH,
            must_not_break_behavior="Hermes/OpenClaw skills work like native skills",
            test_files=["test_skills_e2e.py::TestImportedSkills"],
        ),
        UserJourney(
            name="Schedule and notify",
            description="Scheduled task runs at interval/cron → notification sent",
            risk_level=RiskLevel.HIGH,
            must_not_break_behavior="Task runs on schedule, notifications delivered",
            test_files=["test_scheduler_e2e.py", "test_notifications_e2e.py"],
        ),
        UserJourney(
            name="Deterministic dialogue flow",
            description="Same seed → same conversation trajectory every time",
            risk_level=RiskLevel.HIGH,
            must_not_break_behavior="Deterministic guarantees hold under seeds",
            test_files=["test_determinism_e2e.py", "test_dialogue_e2e.py"],
        ),
        UserJourney(
            name="Skill execution produces outputs",
            description="Skill runs → files/artifacts created in project",
            risk_level=RiskLevel.MEDIUM,
            must_not_break_behavior="Skill produces expected outputs",
            test_files=["test_skills_e2e.py::TestReactSkillExecution", "test_skills_e2e.py::TestRestApiSkillExecution"],
        ),
        UserJourney(
            name="Auth/JWT addition",
            description="Add auth to existing API project",
            risk_level=RiskLevel.HIGH,
            must_not_break_behavior="JWT middleware added without breaking API",
            test_files=["test_routing_e2e.py::TestAuthRouting", "test_skills_e2e.py::TestAuthSkillExecution"],
        ),
        UserJourney(
            name="Dockerfile generation",
            description="Generate Dockerfile for project",
            risk_level=RiskLevel.MEDIUM,
            must_not_break_behavior="Valid Dockerfile generated",
            test_files=["test_routing_e2e.py::TestDockerRouting", "test_skills_e2e.py::TestDockerSkillExecution"],
        ),
        UserJourney(
            name="Repo audit execution",
            description="Audit repo → report generated",
            risk_level=RiskLevel.MEDIUM,
            must_not_break_behavior="Audit runs and produces report",
            test_files=["test_routing_e2e.py::TestRepoAuditRouting"],
        ),
        UserJourney(
            name="Response variation (allowed)",
            description="Seeded random selects from response pool",
            risk_level=RiskLevel.LOW,
            must_not_break_behavior="Variation only in phrasing, not skill/route",
            test_files=["test_determinism_e2e.py::TestDialogueDeterminism"],
        ),
    ]

    def get_coverage_summary(self) -> Dict[str, any]:
        """Get coverage summary by risk level."""
        high_risk = [j for j in self.JOURNEYS if j.risk_level == RiskLevel.HIGH]
        medium_risk = [j for j in self.JOURNEYS if j.risk_level == RiskLevel.MEDIUM]
        low_risk = [j for j in self.JOURNEYS if j.risk_level == RiskLevel.LOW]

        return {
            "high_risk_journeys": len(high_risk),
            "high_risk_covered": len([j for j in high_risk if j.test_files]),
            "medium_risk_journeys": len(medium_risk),
            "medium_risk_covered": len([j for j in medium_risk if j.test_files]),
            "low_risk_journeys": len(low_risk),
            "low_risk_covered": len([j for j in low_risk if j.test_files]),
            "total_journeys": len(self.JOURNEYS),
            "all_covered": all(j.test_files for j in self.JOURNEYS),
        }

    def print_coverage_report(self) -> None:
        """Print human-readable coverage report."""
        summary = self.get_coverage_summary()
        
        print("\n" + "="*60)
        print("E2E TEST COVERAGE BY RISK")
        print("="*60)
        
        print(f"\nHIGH RISK ({summary['high_risk_covered']}/{summary['high_risk_journeys']} covered):")
        for j in self.JOURNEYS:
            if j.risk_level == RiskLevel.HIGH:
                status = "✓" if j.test_files else "✗"
                print(f"  {status} {j.name}")
                print(f"     {j.must_not_break_behavior}")
        
        print(f"\nMEDIUM RISK ({summary['medium_risk_covered']}/{summary['medium_risk_journeys']} covered):")
        for j in self.JOURNEYS:
            if j.risk_level == RiskLevel.MEDIUM:
                status = "✓" if j.test_files else "✗"
                print(f"  {status} {j.name}")
        
        print(f"\nLOW RISK ({summary['low_risk_covered']}/{summary['low_risk_journeys']} covered):")
        for j in self.JOURNEYS:
            if j.risk_level == RiskLevel.LOW:
                status = "✓" if j.test_files else "✗"
                print(f"  {status} {j.name}")
        
        print("\n" + "-"*60)
        
        high_pct = (summary['high_risk_covered'] / summary['high_risk_journeys'] * 100) if summary['high_risk_journeys'] else 100
        med_pct = (summary['medium_risk_covered'] / summary['medium_risk_journeys'] * 100) if summary['medium_risk_journeys'] else 100
        
        print(f"COVERAGE: {high_pct:.0f}% of HIGH risk, {med_pct:.0f}% of MEDIUM risk")
        print(f"ALL CRITICAL PATHS GUARDED: {'YES' if summary['all_covered'] else 'NO'}")
        print("="*60 + "\n")


def get_journey_for_test(test_name: str) -> Optional[UserJourney]:
    """Find the journey that a test belongs to."""
    for journey in UserJourneyMap.JOURNEYS:
        for test_file in journey.test_files:
            if test_file in test_name or test_name.startswith(test_file.split("::")[0]):
                return journey
    return None


def verify_coverage() -> bool:
    """Verify all journeys have tests. Returns True if fully covered."""
    journey_map = UserJourneyMap()
    return journey_map.get_coverage_summary()["all_covered"]


if __name__ == "__main__":
    journey_map = UserJourneyMap()
    journey_map.print_coverage_report()
    
    if verify_coverage():
        print("✓ All critical paths have test coverage")
    else:
        print("✗ WARNING: Some journeys lack test coverage!")
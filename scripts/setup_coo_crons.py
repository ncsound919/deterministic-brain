"""COO Brain cron tasks — autonomous portfolio operations."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

CRON_PATH = os.path.join(os.path.dirname(__file__), "..", ".cron_schedule.json")


def load_crons() -> dict:
    with open(CRON_PATH) as f:
        return json.load(f)


def save_crons(data: dict):
    with open(CRON_PATH, "w") as f:
        json.dump(data, f, indent=4)


def add_coo_crons():
    """Add COO Brain-specific cron tasks to the schedule."""
    data = load_crons()

    coo_tasks = {
        "coo-portfolio-health-check": {
            "name": "coo-portfolio-health-check",
            "skill": "coo-health-check",
            "trigger_type": "interval",
            "interval_seconds": 900,
            "inputs": {
                "action": "run_health_check",
                "products": ["claw-protect", "openhub", "ul2", "aetherdesk", "bbtech"],
            },
            "enabled": True,
            "description": "Every 15 minutes — Check all portfolio products for build failures, exceptions, and security alerts.",
        },
        "coo-github-issue-triage": {
            "name": "coo-github-issue-triage",
            "skill": "coo-issue-triage",
            "trigger_type": "interval",
            "interval_seconds": 1800,
            "inputs": {
                "action": "triage_open_issues",
                "labels": ["coo-brain", "yellow", "red"],
            },
            "enabled": True,
            "description": "Every 30 minutes — Triage open COO Brain issues, auto-close resolved, escalate stale.",
        },
        "coo-stripe-revenue-check": {
            "name": "coo-stripe-revenue-check",
            "skill": "coo-revenue-check",
            "trigger_type": "cron",
            "cron_expr": "0 */4 * * *",
            "inputs": {
                "action": "check_revenue",
                "products": ["claw-protect", "ul2"],
            },
            "enabled": True,
            "description": "Every 4 hours — Check Stripe for payment failures, cancellations, and MRR changes.",
        },
        "coo-dependency-security-scan": {
            "name": "coo-dependency-security-scan",
            "skill": "coo-security-scan",
            "trigger_type": "cron",
            "cron_expr": "0 3 * * *",
            "inputs": {
                "action": "scan_dependencies",
                "products": ["claw-protect", "openhub", "ul2"],
            },
            "enabled": True,
            "description": "3 AM EST daily — Scan all repos for dependency vulnerabilities and security advisories.",
        },
        "coo-daily-briefing": {
            "name": "coo-daily-briefing",
            "skill": "coo-daily-briefing",
            "trigger_type": "cron",
            "cron_expr": "0 7 * * *",
            "inputs": {
                "action": "generate_briefing",
                "include": ["health", "revenue", "momentum", "pending_decisions"],
            },
            "enabled": True,
            "description": "7 AM EST daily — Generate daily portfolio briefing: health, revenue, open issues, pending decisions.",
        },
        "coo-weekly-audit": {
            "name": "coo-weekly-audit",
            "skill": "coo-weekly-audit",
            "trigger_type": "cron",
            "cron_expr": "0 2 * * 0",
            "inputs": {
                "action": "full_audit",
                "products": ["claw-protect", "openhub", "ul2", "aetherdesk", "bbtech"],
            },
            "enabled": True,
            "description": "Sunday 2 AM EST — Full portfolio audit: code quality, security, dependencies, CI status.",
        },
        "coo-auto-fix-green": {
            "name": "coo-auto-fix-green",
            "skill": "coo-auto-fix",
            "trigger_type": "interval",
            "interval_seconds": 300,
            "inputs": {
                "action": "execute_green_zone",
                "max_fixes_per_run": 5,
            },
            "enabled": True,
            "description": "Every 5 minutes — Auto-execute green-zone fixes: cache clears, dependency updates, lint fixes.",
        },
        "coo-stale-issue-cleanup": {
            "name": "coo-stale-issue-cleanup",
            "skill": "coo-cleanup",
            "trigger_type": "cron",
            "cron_expr": "0 4 * * *",
            "inputs": {
                "action": "cleanup_stale_issues",
                "stale_days": 7,
            },
            "enabled": True,
            "description": "4 AM EST daily — Close stale COO Brain issues older than 7 days with no human response.",
        },
    }

    data["tasks"].update(coo_tasks)
    save_crons(data)
    print(f"Added {len(coo_tasks)} COO Brain cron tasks to .cron_schedule.json")
    return coo_tasks


if __name__ == "__main__":
    added = add_coo_crons()
    for name, task in added.items():
        print(f"  ✓ {name}: {task['description']}")

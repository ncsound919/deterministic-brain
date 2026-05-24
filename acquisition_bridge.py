"""
Acquisition Tracker Bridge
==========================
Connects the Deterministic-Brain's AGI autonomous operations
to the acquisition tracker system.

The brain already runs 24/7. This bridge teaches it to:
1. Log daily progress from autonomous activity
2. Update portfolio metrics from health checks
3. Record market insights from news scans
4. Track trend detections from the self-learning loop

Usage:
    from acquisition_bridge import AcquisitionBridge
    bridge = AcquisitionBridge()
    bridge.log_autonomous_session()
    bridge.update_portfolio_status()
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TRACKER_DIR = Path(__file__).parent.parent / ".acquisition-tracker"


class AcquisitionBridge:
    """Bridges brain's autonomous ops into the acquisition tracker."""

    def __init__(self, tracker_dir: Optional[Path] = None, auto_init: bool = True):
        self.tracker_dir = Path(tracker_dir or TRACKER_DIR)
        self.tracker_dir.mkdir(parents=True, exist_ok=True)
        if auto_init:
            self._ensure_initialized()

    def _safe_read(self, filepath: Path) -> str:
        try:
            return filepath.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _ensure_initialized(self) -> None:
        """Create tracker files with header if they don't exist."""
        files = {
            "AGENDA.md": "# Billion Dollar Acquisition Trap — Master Agenda\n\n## Mission\nBuild a portfolio of independent, medium-coupled AI ventures — each a standalone billion-dollar threat.\n",
            "DAILY-LOG.md": "# Daily Progress Log\n\n## Archive\n\n",
            "PROGRESS.md": "# Portfolio Progress Dashboard\n\n## Overall Portfolio Status\n\n| Asset | Deploy Readiness | Build | Tests | Env | Docker | Last Updated |\n|-------|:-:|:-:|:-:|:-:|:-:|:-:|\n\n## Progress Over Time\n\n| Date | Overall % | Δ | Key Milestone |\n|------|:-:|:-:|--------------|\n",
            "INSIGHTS.md": "# Market Intelligence & Strategic Insights\n\n## Trend Detection Log\n\n| Date | Signal | Implication | Action |\n|------|--------|-------------|--------|\n",
            "METRICS.md": "# Acquisition Track Metrics\n\n| Component | Score | Notes |\n|-----------|:-:|-------|\n| **Composite Score** | **—** | Initializing |\n",
        }
        for name, header in files.items():
            filepath = self.tracker_dir / name
            if not filepath.exists():
                filepath.write_text(header, encoding="utf-8")

    def log_autonomous_session(self, data: Dict[str, Any]) -> None:
        """Log an autonomous session to DAILY-LOG.md."""
        log_file = self.tracker_dir / "DAILY-LOG.md"
        today = date.today().isoformat()
        content = self._safe_read(log_file)

        entry = (
            f"\n### {today} — Autonomous Session\n"
            f"- **Brain State**: {data.get('brain_state', 'unknown')}\n"
            f"- **Tasks Executed**: {data.get('tasks_executed', 0)}\n"
            f"- **Trends Detected**: {data.get('trends_detected', 0)}\n"
            f"- **Portfolio Pulse**: {data.get('portfolio_pulse', 'stable')}\n"
        )

        # Insert after header, before archive
        marker = "## Archive"
        if marker in content:
            content = content.replace(marker, f"{entry}\n\n{marker}")
        else:
            content += f"\n{entry}\n"

        log_file.write_text(content, encoding="utf-8")
        logger.info("Logged autonomous session to DAILY-LOG.md")

    def update_portfolio_progress(self, assets: Dict[str, Dict[str, Any]]) -> None:
        """Update deploy readiness and sprint items in PROGRESS.md."""
        progress_file = self.tracker_dir / "PROGRESS.md"
        today = date.today().isoformat()
        content = self._safe_read(progress_file)

        # Build status table
        rows = []
        for asset_name, status in assets.items():
            deploy = status.get("deploy_readiness", "—")
            build = "✅" if status.get("build") else "⚠️"
            tests = "✅" if status.get("tests") else "⚠️"
            env = "✅" if status.get("env") else "⚠️"
            docker = "✅" if status.get("docker") else "⚠️"
            rows.append(f"| **{asset_name}** | **{deploy}** | {build} | {tests} | {env} | {docker} | {today} |")

        table_header = (
            "| Asset | Deploy Readiness | Build | Tests | Env | Docker | Last Updated |\n"
            "|-------|:-:|:-:|:-:|:-:|:-:|:-:|"
        )

        marker = "## Progress Over Time"
        new_table = f"{table_header}\n" + "\n".join(rows)

        if "| Asset | Deploy Readiness |" in content:
            # Replace existing table
            lines = content.split("\n")
            in_table = False
            new_lines = []
            header_written = False
            for line in lines:
                if line.startswith("| Asset | Deploy Readiness |"):
                    in_table = True
                    new_lines.append(table_header)
                    new_lines.extend(rows)
                    header_written = True
                elif in_table and line.startswith("| **"):
                    continue  # skip old rows
                elif in_table and line.startswith("|---|---"):
                    continue
                elif in_table and line.startswith("|"):
                    continue
                else:
                    if in_table and not header_written:
                        new_lines.append(table_header)
                        new_lines.extend(rows)
                        header_written = True
                    in_table = False
                    new_lines.append(line)
            content = "\n".join(new_lines)
        elif marker in content:
            content = content.replace(marker, f"{new_table}\n\n{marker}")
        else:
            content = f"{new_table}\n\n{marker}\n"

        progress_file.write_text(content, encoding="utf-8")
        logger.info("Updated portfolio progress in PROGRESS.md")

    def record_insight(self, signal_type: str, signal: str, implication: str, action: str) -> None:
        """Record a detected market signal or strategic insight."""
        insights_file = self.tracker_dir / "INSIGHTS.md"
        today = date.today().isoformat()
        content = self._safe_read(insights_file)

        entry = f"| {today} | **{signal_type}**: {signal} | {implication} | {action} |"

        # Find the trend detection log table
        marker = "## Trend Detection Log"
        table_found = False
        lines = content.split("\n")
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if line.strip() == marker:
                # Find the table header + separator lines, insert after them
                remaining = lines[i+1:]
                for j, next_line in enumerate(remaining):
                    new_lines.append(next_line)
                    if next_line.strip().startswith("|---"):
                        new_lines.append(entry)
                        # Copy remaining lines
                        new_lines.extend(remaining[j+1:])
                        table_found = True
                        break
                break

        if table_found:
            content = "\n".join(new_lines)
        else:
            content += f"\n\n## Trend Detection Log\n| Date | Signal | Implication | Action |\n|------|--------|-------------|--------|\n{entry}\n"

        insights_file.write_text(content, encoding="utf-8")
        logger.info("Recorded insight in INSIGHTS.md: %s", signal)

    def refresh_metrics(self, scores: Dict[str, float]) -> None:
        """Update portfolio health scores in METRICS.md."""
        metrics_file = self.tracker_dir / "METRICS.md"
        today = date.today().isoformat()
        content = self._safe_read(metrics_file)
        lines = content.split("\n")

        for component, score in scores.items():
            found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"| **{component}** |") or stripped.startswith(f"| {component} |"):
                    parts = stripped.split(" |")
                    if len(parts) >= 3:
                        parts[1] = f" {score}%"
                        indent = line[:len(line) - len(line.lstrip())]
                        lines[i] = indent + " |".join(parts)
                        found = True
                    break
            if not found:
                lines.append(f"| {component} | {score}% | — | Auto-updated {today} |")

        content = "\n".join(lines)
        metrics_file.write_text(content, encoding="utf-8")
        logger.info("Refreshed metrics in METRICS.md")

    def scan_and_sync(self) -> Dict[str, Any]:
        """Full autonomous scan: check system, update tracker, return status."""
        results = {}

        try:
            from brain.health_check import run_health_check
            health = run_health_check()
            results["health"] = {
                "passed": health.passed,
                "checks_run": len(health.checks),
                "errors": health.errors,
            }
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            results["health"] = {"passed": False, "error": str(e)}

        try:
            from brain.autodream import run_autodream
            dream = run_autodream(dry_run=True)
            results["autodream"] = {"status": "completed"}
        except Exception as e:
            logger.warning("Autodream failed: %s", e)
            results["autodream"] = {"status": "failed", "error": str(e)}

        return results

    def get_status(self) -> Dict[str, Any]:
        """Get current bridge status."""
        return {
            "tracker_dir": str(self.tracker_dir),
            "files_present": all(
                (self.tracker_dir / f).exists()
                for f in ["AGENDA.md", "DAILY-LOG.md", "PROGRESS.md", "INSIGHTS.md", "METRICS.md"]
            ),
            "last_sync": datetime.now().isoformat(),
        }

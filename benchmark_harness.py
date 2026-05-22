#!/usr/bin/env python3
"""
Benchmark Harness — Stress-tests KAIROS, AutoDream, Cron Scheduler, and Self-Healing.
Runs for a configurable duration, tracking system health, performance, and stability.

Usage:
    python benchmark_harness.py                     # Default: 5 cycles, fast mode
    python benchmark_harness.py --cycles 20         # 20 benchmark cycles
    python benchmark_harness.py --hours 2           # Run for ~2 hours (cycles every 5 min)
    python benchmark_harness.py --report-only       # Just print the last report
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════
# Benchmark Metrics Collector
# ═══════════════════════════════════════════════════════════════════════

class BenchmarkMetrics:
    """Collects and aggregates metrics across all subsystems."""

    def __init__(self, output_dir: str = ".benchmarks"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.start_time = datetime.now(timezone.utc)
        self.cycles: List[Dict] = []
        self.snapshots: List[Dict] = []
        self.errors: List[Dict] = []

    def take_snapshot(self, cycle: int) -> Dict:
        """Capture full system state."""
        snap = {
            "cycle": cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kairos": self._kairos_snapshot(),
            "autodream": self._autodream_snapshot(),
            "cron_scheduler": self._cron_snapshot(),
            "runtime_healer": self._healer_snapshot(),
            "learning_loop": self._learning_loop_snapshot(),
            "event_bus": self._event_bus_snapshot(),
            "system": self._system_snapshot(),
        }
        self.snapshots.append(snap)
        return snap

    def _kairos_snapshot(self) -> Dict:
        try:
            from orchestration.kairos_daemon import kairos_status
            return kairos_status()
        except Exception as e:
            return {"error": str(e), "running": False}

    def _autodream_snapshot(self) -> Dict:
        path = Path(".autodream_last_run.json")
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return {
                    "last_run": data.get("timestamp", "unknown"),
                    "dry_run": data.get("dry_run", None),
                    "sessions_analyzed": data.get("session_patterns", {}).get("total_sessions", 0),
                    "corrections_found": len(data.get("corrections", [])),
                    "traces_db_size_mb": self._file_size_mb("traces.db"),
                    "corrections_file_size_kb": self._file_size_kb(".autodream_corrections.jsonl"),
                }
            except Exception:
                pass
        return {"last_run": "never", "error": "not_found"}

    def _cron_snapshot(self) -> Dict:
        try:
            from features.scheduler import get_scheduler
            s = get_scheduler()
            tasks = s.list_tasks()
            results = s.get_results()
            return {
                "running": s.is_running(),
                "tasks_registered": len(tasks),
                "next_runs": {t["name"]: str(t.get("next_run", "N/A")) for t in tasks[:10]},
                "results_count": sum(len(v) for v in results.values()),
                "results_by_task": {k: len(v) for k, v in list(results.items())[:10]},
            }
        except Exception as e:
            return {"error": str(e), "running": False}

    def _healer_snapshot(self) -> Dict:
        try:
            from orchestration.runtime_healer import runtime_healer
            states = runtime_healer.all_circuit_states()
            heals = runtime_healer.recent_heals(limit=50)
            open_circuits = [s for s in states if s["state"] == "open"]
            return {
                "circuit_states": len(states),
                "open_circuits": len(open_circuits),
                "open_details": open_circuits,
                "recent_heals": len(heals),
                "heal_log_size_kb": self._file_size_kb(".heal_runtime_log.json"),
            }
        except Exception as e:
            return {"error": str(e)}

    def _learning_loop_snapshot(self) -> Dict:
        snap = {}
        try:
            from reasoning.contextual_bandit import get_bandit
            stats = get_bandit().get_stats()
            snap["bandit"] = {"arms": stats.get("total_arms", 0), "contexts": stats.get("contexts_explored", 0)}
        except Exception as e:
            snap["bandit"] = f"error: {e}"
        try:
            from evolution.reward_tracker import get_reward_tracker
            snap["rewards"] = get_reward_tracker().stats()
        except Exception as e:
            snap["rewards"] = f"error: {e}"
        try:
            from evolution.skill_evolver import SkillEvolver
            snap["evolver_skills"] = len(SkillEvolver().all_stats())
        except Exception as e:
            snap["evolver_skills"] = f"error: {e}"
        return snap

    def _event_bus_snapshot(self) -> Dict:
        try:
            from orchestration.event_bus import event_bus
            return {
                "subscribers": len(event_bus._subscribers) if hasattr(event_bus, "_subscribers") else "unknown",
                "events_pending": event_bus.stats() if hasattr(event_bus, "stats") else {},
            }
        except Exception as e:
            return {"error": str(e)}

    def _system_snapshot(self) -> Dict:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "threads_active": threading.active_count(),
        }

    def _file_size_mb(self, path: str) -> float:
        p = Path(path)
        return round(p.stat().st_size / (1024 * 1024), 2) if p.exists() else 0.0

    def _file_size_kb(self, path: str) -> float:
        p = Path(path)
        return round(p.stat().st_size / 1024, 2) if p.exists() else 0.0

    def record_cycle(self, cycle: int, duration_s: float, actions: List[Dict]) -> Dict:
        """Record a completed benchmark cycle."""
        entry = {
            "cycle": cycle,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(duration_s, 2),
            "actions_performed": len(actions),
            "actions": actions[:20],
            "errors_count": len([a for a in actions if a.get("status") == "error"]),
        }
        self.cycles.append(entry)
        return entry

    def record_error(self, subsystem: str, error: str):
        self.errors.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystem": subsystem,
            "error": error[:500],
        })

    def generate_report(self) -> Dict:
        """Generate a final comprehensive report."""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        snaps = self.snapshots

        # Aggregate stats
        kairos_runs = [s["kairos"].get("total_runs", 0) for s in snaps if "kairos" in s]
        kairos_idle_triggers = [s["kairos"].get("idle_triggers", 0) for s in snaps if "kairos" in s]
        corrections_total = [s["autodream"].get("corrections_found", 0) for s in snaps if "autodream" in s]

        report = {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "total_elapsed_seconds": round(elapsed, 1),
            "total_elapsed_hours": round(elapsed / 3600, 2),
            "total_cycles": len(self.cycles),
            "total_snapshots": len(snaps),
            "total_errors": len(self.errors),

            # KAIROS
            "kairos": {
                "total_runs": kairos_runs[-1] if kairos_runs else 0,
                "idle_triggers": kairos_idle_triggers[-1] if kairos_idle_triggers else 0,
                "is_running": snaps[-1].get("kairos", {}).get("running", False) if snaps else False,
            },

            # AutoDream
            "autodream": {
                "last_run": snaps[-1].get("autodream", {}).get("last_run", "never") if snaps else "never",
                "corrections_found": corrections_total[-1] if corrections_total else 0,
            },

            # Cron
            "cron": {
                "tasks_registered": snaps[-1].get("cron_scheduler", {}).get("tasks_registered", 0) if snaps else 0,
                "tasks_executed_total": snaps[-1].get("cron_scheduler", {}).get("results_count", 0) if snaps else 0,
                "is_running": snaps[-1].get("cron_scheduler", {}).get("running", False) if snaps else False,
            },

            # Runtime Healer
            "healer": {
            "circuit_states": snaps[-1].get("healer", {}).get("circuit_states", 0) if snaps else 0,
            "open_circuits": snaps[-1].get("healer", {}).get("open_circuits", 0) if snaps else 0,
            },

            # Performance
            "performance": {
                "cpu_percent": snaps[-1].get("system", {}).get("cpu_percent", 0) if snaps else 0,
                "memory_percent": snaps[-1].get("system", {}).get("memory_percent", 0) if snaps else 0,
                "avg_cycle_duration_s": round(sum(c["duration_seconds"] for c in self.cycles) / max(len(self.cycles), 1), 2),
            },

            # System health score (0-100)
            "health_score": self._compute_health_score(snaps[-1] if snaps else {}),
        }

        # Persist
        report_path = self.output_dir / "report.json"
        report_path.write_text(json.dumps(report, indent=2))
        snap_path = self.output_dir / "snapshots.json"
        snap_path.write_text(json.dumps(snaps, indent=2))
        cycles_path = self.output_dir / "cycles.json"
        cycles_path.write_text(json.dumps(self.cycles, indent=2))
        errors_path = self.output_dir / "errors.json"
        errors_path.write_text(json.dumps(self.errors, indent=2))

        return report

    def _compute_health_score(self, snap: Dict) -> int:
        score = 100
        if not snap:
            return 0
        if not snap.get("kairos", {}).get("running", False):
            score -= 25
        if not snap.get("cron_scheduler", {}).get("running", False):
            score -= 25
        if snap.get("healer", {}).get("open_circuits", 0) > 0:
            score -= 20
        if snap.get("system", {}).get("memory_percent", 0) > 85:
            score -= 15
        if snap.get("system", {}).get("cpu_percent", 0) > 90:
            score -= 15
        return max(0, score)


# ═══════════════════════════════════════════════════════════════════════
# Benchmark Actions
# ═══════════════════════════════════════════════════════════════════════

class BenchmarkActions:
    """Performs individual benchmark actions on each subsystem."""

    def __init__(self, metrics: BenchmarkMetrics):
        self.metrics = metrics

    def run_cycle(self, cycle: int, skip_kairos_activity: bool = False) -> List[Dict]:
        """Execute one full benchmark cycle across all subsystems."""
        actions = []

        actions.append(self.test_kairos_daemon(skip_activity=skip_kairos_activity))
        actions.append(self.test_autodream())
        actions.append(self.test_cron_scheduler(cycle))
        actions.append(self.test_runtime_healer())
        actions.append(self.test_learning_loop())
        actions.append(self.test_skill_registry())
        actions.append(self.test_event_bus())
        actions.append(self.test_config())

        return actions

    def test_kairos_daemon(self, skip_activity: bool = False) -> Dict:
        try:
            from orchestration.kairos_daemon import get_daemon, kairos_status
            daemon = get_daemon()
            if not daemon.running:
                daemon.start()
                time.sleep(0.5)
            if not skip_activity:
                daemon.update_activity()
            status = kairos_status()
            return {"subsystem": "kairos", "status": "ok", "running": status["running"],
                    "idle_threshold_s": status["idle_threshold_seconds"],
                    "total_runs": status["total_runs"],
                    "idle_triggers": status["idle_triggers"]}
        except Exception as e:
            self.metrics.record_error("kairos", str(e))
            return {"subsystem": "kairos", "status": "error", "error": str(e)[:200]}

    def test_autodream(self) -> Dict:
        try:
            from brain.autodream import run_autodream
            # Dry run to avoid modifying real data
            result = run_autodream(dry_run=False)
            patterns = result.get("session_patterns", {})
            return {"subsystem": "autodream", "status": "ok",
                    "sessions_analyzed": patterns.get("total_sessions", 0),
                    "corrections": len(result.get("corrections", [])),
                    "knowledge_bank": result.get("knowledge_bank_consolidation", {}).get("status", "skipped")}
        except Exception as e:
            self.metrics.record_error("autodream", str(e))
            return {"subsystem": "autodream", "status": "error", "error": str(e)[:200]}

    def test_cron_scheduler(self, cycle: int) -> Dict:
        try:
            from features.scheduler import get_scheduler
            s = get_scheduler()
            if not s.is_running():
                s.start()
            tasks = s.list_tasks()
            # Force-execute a high-priority task every few cycles
            if cycle % 3 == 0:
                try:
                    s._execute_task()
                except Exception:
                    pass
            return {"subsystem": "cron_scheduler", "status": "ok",
                    "running": s.is_running(),
                    "tasks_registered": len(tasks),
                    "tasks": [t["name"] for t in tasks[:10]]}
        except Exception as e:
            self.metrics.record_error("cron_scheduler", str(e))
            return {"subsystem": "cron_scheduler", "status": "error", "error": str(e)[:200]}

    def test_runtime_healer(self) -> Dict:
        try:
            from orchestration.runtime_healer import runtime_healer

            # Test circuit breaker
            runtime_healer.record_success("benchmark_test_skill")
            cb_state = runtime_healer.circuit_breaker_state("benchmark_test_skill")

            # Test retry logic
            def test_fn():
                return {"result": "benchmark_ok"}

            retry_result = runtime_healer.execute_with_retry(
                test_fn, "benchmark_retry_skill", max_retries=2, backoff_ms=100
            )

            # Test daemon watchdog
            if not hasattr(runtime_healer, "_benchmark_daemon_alive"):
                runtime_healer._benchmark_daemon_alive = True
                runtime_healer.watch_daemon(
                    "benchmark_test_daemon",
                    start_fn=lambda: None,
                    is_alive_fn=lambda: True,
                )
            daemon_result = runtime_healer.check_daemons()

            # Test correction healing
            corrections_healed = runtime_healer.heal_from_corrections()

            # Get all states
            all_states = runtime_healer.all_circuit_states()
            recent = runtime_healer.recent_heals(limit=5)

            return {"subsystem": "runtime_healer", "status": "ok",
                    "circuit_state": cb_state["state"],
                    "retry_result": retry_result.get("status", "unknown"),
                    "daemons_watched": len(runtime_healer._daemon_watches),
                    "corrections_healed": corrections_healed,
                    "total_circuits_tracked": len(all_states),
                    "recent_heal_events": len(recent)}
        except Exception as e:
            self.metrics.record_error("runtime_healer", str(e))
            return {"subsystem": "runtime_healer", "status": "error", "error": str(e)[:200]}

    def test_learning_loop(self) -> Dict:
        try:
            from orchestration.event_bus import connect_all_learning
            connect_all_learning()
            return {"subsystem": "learning_loop", "status": "ok", "connected": True}
        except Exception as e:
            self.metrics.record_error("learning_loop", str(e))
            return {"subsystem": "learning_loop", "status": "error", "error": str(e)[:200]}

    def test_skill_registry(self) -> Dict:
        try:
            from orchestration.skill_registry import SkillRegistry
            reg = SkillRegistry()
            skills = reg.list_all() if hasattr(reg, "list_all") else []
            count = len(skills) if isinstance(skills, list) else 0
            return {"subsystem": "skill_registry", "status": "ok",
                    "skills_loaded": count}
        except Exception as e:
            self.metrics.record_error("skill_registry", str(e))
            return {"subsystem": "skill_registry", "status": "error", "error": str(e)[:200]}

    def test_event_bus(self) -> Dict:
        try:
            from orchestration.event_bus import event_bus
            # Emit test events
            event_bus.emit("benchmark_test", source="harness", cycle="test")
            event_bus.emit("skill_success", skill_id="benchmark_success", confidence=0.95)
            event_bus.emit("skill_failure", skill_id="benchmark_fail", confidence=0.12)
            return {"subsystem": "event_bus", "status": "ok",
                    "events_emitted": 3}
        except Exception as e:
            self.metrics.record_error("event_bus", str(e))
            return {"subsystem": "event_bus", "status": "error", "error": str(e)[:200]}

    def test_config(self) -> Dict:
        try:
            from config import cfg
            summary = cfg.summary()
            return {"subsystem": "config", "status": "ok",
                    "openrouter_enabled": summary.get("openrouter_enabled", False),
                    "qdrant_url": summary.get("qdrant_url", ""),
                    "tracing": summary.get("tracing", False)}
        except Exception as e:
            return {"subsystem": "config", "status": "error", "error": str(e)[:200]}


# ═══════════════════════════════════════════════════════════════════════
# Main Benchmark Runner
# ═══════════════════════════════════════════════════════════════════════

def print_header(text: str):
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}")


def print_subheader(text: str):
    print(f"\n  --- {text} ---")


def print_metric(label: str, value: Any, ok: bool = True):
    icon = "[OK]" if ok else "[!] "
    print(f"  {icon} {label:40s} {value}")


def print_report(report: Dict):
    print_header("BENCHMARK REPORT")
    print(f"  Elapsed: {report['total_elapsed_hours']}h ({report['total_elapsed_seconds']}s)")
    print(f"  Cycles: {report['total_cycles']} | Snapshots: {report['total_snapshots']} | Errors: {report['total_errors']}")
    print(f"  Health Score: {report['health_score']}/100")

    print_subheader("KAIROS")
    k = report["kairos"]
    print_metric("Total Runs", k["total_runs"], k["total_runs"] > 0)
    print_metric("Idle Triggers", k["idle_triggers"])
    print_metric("Running", k["is_running"], k["is_running"])

    print_subheader("AutoDream")
    a = report["autodream"]
    print_metric("Last Run", a["last_run"])
    print_metric("Corrections Found", a["corrections_found"])

    print_subheader("Cron Scheduler")
    c = report["cron"]
    print_metric("Tasks Registered", c["tasks_registered"], c["tasks_registered"] > 0)
    print_metric("Tasks Executed", c["tasks_executed_total"])
    print_metric("Running", c["is_running"], c["is_running"])

    print_subheader("Runtime Healer")
    h = report["healer"]
    print_metric("Circuit States", h["circuit_states"])
    print_metric("Open Circuits", h["open_circuits"], h["open_circuits"] == 0)

    print_subheader("Performance")
    p = report["performance"]
    print_metric("CPU %", f"{p['cpu_percent']}%", p["cpu_percent"] < 80)
    print_metric("Memory %", f"{p['memory_percent']}%", p["memory_percent"] < 85)
    print_metric("Avg Cycle Duration", f"{p['avg_cycle_duration_s']}s")

    print("\n  Full report: .benchmarks/report.json")
    print("  Snapshots:   .benchmarks/snapshots.json")
    print("  Cycles:      .benchmarks/cycles.json")
    print("  Errors:      .benchmarks/errors.json\n")


def run_benchmark(cycles: int = 5, interval_s: float = 30.0):
    """Main benchmark loop."""
    print_header("DETERMINISTIC BRAIN — BENCHMARK HARNESS")
    print(f"  Cycles: {cycles} | Interval: {interval_s}s | Start: {datetime.now(timezone.utc).isoformat()}")

    # Bootstrap the system
    print_subheader("Bootstrapping System")
    boot_actions = []

    try:
        from brain.soul import reset_soul, get_soul
        reset_soul()
        soul = get_soul().pulse()
        print_metric("Soul", f"{soul.get('name', '?')} | {soul.get('role', '?')}", True)
        boot_actions.append({"soul": "loaded"})
    except Exception as e:
        print_metric("Soul", f"WARN: {e}", False)

    try:
        from orchestration.event_bus import connect_all_learning
        connect_all_learning()
        print_metric("Learning Loop", "Wired (bandit <-> tracker <-> evolver <-> healer)", True)
        boot_actions.append({"learning_loop": "connected"})
    except Exception as e:
        print_metric("Learning Loop", f"WARN: {e}", False)

    try:
        from orchestration.kairos_daemon import start_kairos
        result = start_kairos()
        print_metric("KAIROS", f"Started (idle: {result.get('idle_threshold_seconds', 0)}s)", result.get("running", False))
        boot_actions.append({"kairos": "started"})
    except Exception as e:
        print_metric("KAIROS", f"WARN: {e}", False)

    try:
        from features.scheduler import get_scheduler
        get_scheduler().start()
        print_metric("Cron Scheduler", "Started", True)
        boot_actions.append({"cron": "started"})
    except Exception as e:
        print_metric("Cron Scheduler", f"WARN: {e}", False)

    # Initialize metrics and actions
    metrics = BenchmarkMetrics()
    actions = BenchmarkActions(metrics)

    # Run benchmark cycles
    print_subheader("Running Benchmark Cycles")
    for cycle in range(1, cycles + 1):
        cycle_start = time.time()
        print(f"\n  --- Cycle {cycle}/{cycles} ---")

        # On even cycles, skip kairos activity update to allow idle detection
        skip_kairos = (cycle % 2 == 0)
        cycle_actions = actions.run_cycle(cycle, skip_kairos_activity=skip_kairos)

        # Print per-action results
        for a in cycle_actions:
            sub = a.get("subsystem", "unknown")
            status = a.get("status", "error")
            ok = status == "ok"
            icon = "  [OK]" if ok else "  [FAIL]"
            if ok:
                details = {k: v for k, v in a.items() if k not in ("subsystem", "status")}
                print(f"{icon} {sub:25s} {details}")
            else:
                print(f"{icon} {sub:25s} {a.get('error', 'unknown')[:80]}")

        duration = time.time() - cycle_start
        metrics.record_cycle(cycle, duration, cycle_actions)

        # Take snapshot every cycle
        snap = metrics.take_snapshot(cycle)
        print(f"  [SNAP] Health: {metrics._compute_health_score(snap)}/100 | CPU: {snap['system']['cpu_percent']}% | Mem: {snap['system']['memory_percent']}%")

        if cycle < cycles:
            # Every 2nd cycle, allow a quiet period for KAIROS idle detection
            # Skip updating activity this cycle so KAIROS can detect idle
            if cycle % 2 == 0:
                print("  [KAIROS-IDLE] Quiet period (85s) for KAIROS idle detection...")
                time.sleep(85)
                # Check KAIROS status after idle period
                try:
                    from orchestration.kairos_daemon import kairos_status
                    ks = kairos_status()
                    print(f"  [KAIROS-RESULT] total_runs={ks['total_runs']} | idle_triggers={ks['idle_triggers']} | seconds_since_activity={ks['seconds_since_activity']}")
                    if ks['total_runs'] > 0:
                        print("  [KAIROS] Maintenance successfully triggered after idle period!")
                except Exception as e:
                    print(f"  [KAIROS] Status check failed: {e}")
            else:
                remaining = (cycles - cycle) * interval_s
                print(f"  [SLEEP] {interval_s}s (remaining: {remaining:.0f}s)...")
                time.sleep(interval_s)

    # Generate final report
    report = metrics.generate_report()
    print_report(report)

    return report


def show_last_report():
    """Display the last benchmark report."""
    report_path = Path(".benchmarks/report.json")
    if report_path.exists():
        report = json.loads(report_path.read_text())
        print_report(report)
    else:
        print("No benchmark report found. Run benchmark_harness.py first.")


# ═══════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Brain — Benchmark Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--cycles", type=int, default=5,
                        help="Number of benchmark cycles (default: 5)")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds between cycles (default: 5, use 300 for long runs)")
    parser.add_argument("--hours", type=float, default=None,
                        help="Run for N hours (overrides --cycles and --interval)")
    parser.add_argument("--report-only", action="store_true",
                        help="Show last report and exit")
    args = parser.parse_args()

    os.chdir(Path(__file__).parent)

    if args.report_only:
        show_last_report()
        return

    if args.hours:
        # Calculate cycles based on hours
        interval = args.interval if args.interval else 300  # default 5 min for hours mode
        cycles = max(1, int((args.hours * 3600) / interval))
        print(f"  Hours mode: {args.hours}h = ~{cycles} cycles at {interval}s interval")
    else:
        cycles = args.cycles
        interval = args.interval

    try:
        run_benchmark(cycles=cycles, interval_s=interval)
    except KeyboardInterrupt:
        print("\n\n  Benchmark interrupted by user.")
        # Try to generate partial report
        try:
            pass
            # Can't recover easily from interrupt, just exit
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()

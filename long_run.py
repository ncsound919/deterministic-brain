#!/usr/bin/env python3
"""
LONG-RUN BENCHMARK — Multi-hour sustained stress test of all subsystems.

Boots the full deterministic brain and cycles through:
  ACTIVE phases  — execute chains (marketing, promotion, networking, SaaS, system)
  PASSIVE phases — idle detection triggers KAIROS maintenance + autoDream
  HEALING phases — circuit breaker tests, correction healing, daemon watchdog
  LEARNING phases— bandit feed, evolver scoring, reward tracking
  METRICS       — snapshots every cycle, full report at end

Usage:
    python long_run.py                     # Default: 12 cycles (~30 min)
    python long_run.py --hours 2           # ~2 hours
    python long_run.py --hours 4           # ~4 hours (thorough burn-in)
    python long_run.py --report-only       # Print last report
"""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
import threading
import warnings
import traceback
from datetime import datetime, timezone
from pathlib import Path

os.chdir(Path(__file__).parent)

if not sys.warnoptions:
    warnings.filterwarnings("ignore")
warnings.filterwarnings("ignore", category=UserWarning,
                        message=r"Api key is used with an insecure connection")
warnings.filterwarnings("ignore", category=UserWarning,
                        message=r"Failed to obtain server version")

REPORT_DIR = Path(".long_run")
REPORT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────
# CHAIN CATEGORIES for staggered execution
# ─────────────────────────────────────────────────────────────────────

CHAIN_CATEGORIES = {
    "marketing": [
        "marketing-social-campaign",
        "marketing-seo-audit",
        "marketing-email-campaign",
        "marketing-competitor-analysis",
        "marketing-growth-hack",
        "marketing-brand-refresh",
    ],
    "promotion": [
        "promotion-product-launch",
        "promotion-cross-promote",
        "promotion-influencer-outreach",
        "promotion-landing-page",
        "promotion-event-marketing",
    ],
    "networking": [
        "networking-github-outreach",
        "networking-twitter-engagement",
        "networking-collab-discovery",
        "networking-community-build",
    ],
    "saas": [
        "saas-fullstack-scaffold",
        "saas-deploy-pipeline",
        "saas-test-suite",
        "saas-monitoring-setup",
        "saas-api-docs-generate",
    ],
    "system": [
        "system-self-audit",
        "system-full-optimize",
        "system-heal-loop",
        "system-expand-skills",
        "system-intelligence-report",
    ],
}

# ─────────────────────────────────────────────────────────────────────
# METRICS COLLECTOR
# ─────────────────────────────────────────────────────────────────────

class LongRunMetrics:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.cycles: List[Dict] = []
        self.errors: List[Dict] = []
        self.chain_history: List[Dict] = []
        self._category_idx = 0

    def next_chain_category(self) -> tuple:
        cats = list(CHAIN_CATEGORIES.keys())
        cat = cats[self._category_idx % len(cats)]
        self._category_idx += 1
        chains = CHAIN_CATEGORIES[cat]
        chain = chains[self._category_idx % len(chains)]
        return cat, chain

    def snapshot(self, cycle_num: int, phase: str) -> Dict:
        snap = {
            "cycle": cycle_num,
            "phase": phase,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # KAIROS
        try:
            from orchestration.kairos_daemon import kairos_status
            k = kairos_status()
            snap["kairos"] = {"running": k["running"], "total_runs": k["total_runs"],
                              "idle_triggers": k["idle_triggers"], "is_idle": k["is_currently_idle"]}
        except Exception as e:
            snap["kairos"] = {"error": str(e)}
        # Cron
        try:
            from features.scheduler import get_scheduler
            s = get_scheduler()
            tasks = s.list_tasks()
            results = s.get_results()
            snap["cron"] = {"running": s.is_running(), "tasks": len(tasks),
                            "total_executions": sum(len(v) for v in results.values())}
        except Exception as e:
            snap["cron"] = {"error": str(e)}
        # Healer
        try:
            from orchestration.runtime_healer import runtime_healer
            states = runtime_healer.all_circuit_states()
            open_c = [s for s in states if s["state"] == "open"]
            snap["healer"] = {"circuits_tracked": len(states), "open": len(open_c),
                              "daemons_watched": len(runtime_healer._daemon_watches),
                              "heal_events": len(runtime_healer.recent_heals(limit=500))}
        except Exception as e:
            snap["healer"] = {"error": str(e)}
        # Learning
        try:
            from reasoning.contextual_bandit import get_bandit
            b = get_bandit().get_stats()
            snap["bandit"] = {"arms": b.get("total_arms", 0), "contexts": b.get("contexts_explored", 0)}
        except Exception as e:
            snap["bandit"] = {"error": str(e)}
        try:
            from evolution.reward_tracker import get_reward_tracker
            r = get_reward_tracker().stats()
            snap["rewards"] = {"sessions": r.get("active_sessions", 0),
                               "conversions": r.get("total_conversions", 0)}
        except Exception as e:
            snap["rewards"] = {"error": str(e)}
        try:
            from evolution.skill_evolver import SkillEvolver
            snap["evolver"] = {"skills": len(SkillEvolver().all_stats())}
        except Exception as e:
            snap["evolver"] = {"error": str(e)}
        # AutoDream
        ap = Path(".autodream_last_run.json")
        if ap.exists():
            ad = json.loads(ap.read_text())
            snap["autodream"] = {"last_run": ad.get("timestamp", "?"),
                                 "sessions": ad.get("session_patterns", {}).get("total_sessions", 0),
                                 "corrections": len(ad.get("corrections", []))}
        else:
            snap["autodream"] = {"last_run": "never"}
        # Event bus
        try:
            from orchestration.event_bus import event_bus
            snap["event_bus"] = {"subscribers": len(getattr(event_bus, "_subscribers", {}))}
        except Exception:
            snap["event_bus"] = {"subscribers": 0}
        # System
        import psutil
        snap["system"] = {"cpu": psutil.cpu_percent(interval=0.1),
                          "mem": psutil.virtual_memory().percent,
                          "threads": threading.active_count()}

        self.cycles.append(snap)
        return snap

    def record_error(self, subsystem: str, error: str):
        self.errors.append({"ts": datetime.now(timezone.utc).isoformat(), "subsystem": subsystem, "error": error[:500]})

    def record_chain(self, category: str, chain: str, result: Dict):
        self.chain_history.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "category": category, "chain": chain,
            "status": result.get("status", "error"),
            "duration_s": result.get("duration_seconds", 0),
            "steps_ok": result.get("steps_ok", 0),
            "steps_total": result.get("steps_total", 0),
        })

    def generate_report(self) -> Dict:
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        snaps = self.cycles
        chains = self.chain_history
        last_snap = snaps[-1] if snaps else {}

        # Aggregate by category
        by_cat = {}
        for c in chains:
            cat = c["category"]
            if cat not in by_cat:
                by_cat[cat] = {"total": 0, "ok": 0, "failed": 0}
            by_cat[cat]["total"] += 1
            if c["status"] == "ok":
                by_cat[cat]["ok"] += 1
            else:
                by_cat[cat]["failed"] += 1

        # Healing stats
        heal_events = sum(s.get("healer", {}).get("heal_events", 0) for s in snaps if s.get("healer"))
        open_circuits_last = last_snap.get("healer", {}).get("open", 0) if last_snap else 0

        # KAIROS
        kairos_runs = [s.get("kairos", {}).get("total_runs", 0) for s in snaps]
        kairos_max = max(kairos_runs) if kairos_runs else 0

        report = {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "elapsed_hours": round(elapsed / 3600, 2),
            "total_cycles": len(snaps),
            "total_chain_executions": len(chains),
            "total_errors": len(self.errors),
            "health_score": self._health_score(last_snap),
            "kairos": {
                "total_maintenance_runs": kairos_max,
                "idle_triggers": max([s.get("kairos", {}).get("idle_triggers", 0) for s in snaps] or [0]),
                "running": last_snap.get("kairos", {}).get("running", False) if last_snap else False,
            },
            "autodream": {
                "last_run": last_snap.get("autodream", {}).get("last_run", "never") if last_snap else "never",
                "corrections_found": max([s.get("autodream", {}).get("corrections", 0) for s in snaps] or [0]),
            },
            "cron": {
                "total_executions": max([s.get("cron", {}).get("total_executions", 0) for s in snaps] or [0]),
                "tasks_registered": last_snap.get("cron", {}).get("tasks", 0) if last_snap else 0,
                "running": last_snap.get("cron", {}).get("running", False) if last_snap else False,
            },
            "healer": {
                "circuits_tracked": max([s.get("healer", {}).get("circuits_tracked", 0) for s in snaps] or [0]),
                "open_circuits": open_circuits_last,
                "heal_events_logged": heal_events,
            },
            "learning": {
                "bandit_arms": last_snap.get("bandit", {}).get("arms", 0) if last_snap else 0,
                "reward_sessions": last_snap.get("rewards", {}).get("sessions", 0) if last_snap else 0,
                "skills_tracked": last_snap.get("evolver", {}).get("skills", 0) if last_snap else 0,
            },
            "chain_results_by_category": by_cat,
            "performance": {
                "cpu_avg": round(sum(s.get("system", {}).get("cpu", 0) for s in snaps) / max(len(snaps), 1), 1),
                "mem_avg": round(sum(s.get("system", {}).get("mem", 0) for s in snaps) / max(len(snaps), 1), 1),
                "mem_last": last_snap.get("system", {}).get("mem", 0) if last_snap else 0,
                "threads_last": last_snap.get("system", {}).get("threads", 0) if last_snap else 0,
            },
        }
        # Persist
        (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2))
        (REPORT_DIR / "snapshots.json").write_text(json.dumps(snaps, indent=2))
        (REPORT_DIR / "chain_history.json").write_text(json.dumps(chains, indent=2))
        (REPORT_DIR / "errors.json").write_text(json.dumps(self.errors, indent=2))
        return report

    def _health_score(self, snap: Dict) -> int:
        score = 100
        if not snap: return 0
        if not snap.get("kairos", {}).get("running", False): score -= 25
        if not snap.get("cron", {}).get("running", False): score -= 25
        if snap.get("healer", {}).get("open", 0) > 0: score -= 20
        if snap.get("system", {}).get("mem", 0) > 85: score -= 15
        if snap.get("system", {}).get("cpu", 0) > 90: score -= 15
        return max(0, score)


# ─────────────────────────────────────────────────────────────────────
# PHASE RUNNERS
# ─────────────────────────────────────────────────────────────────────

def print_banner(text: str):
    print(f"\n{'=' * 68}", flush=True)
    print(f"  {text}", flush=True)
    print(f"{'=' * 68}", flush=True)


def print_step(icon: str, text: str):
    print(f"  [{icon}] {text}", flush=True)


def boot_system() -> Dict:
    print_banner("BOOTING DETERMINISTIC BRAIN")
    boot = {}

    try:
        from brain.soul import reset_soul, get_soul
        reset_soul()
        soul = get_soul().pulse()
        print_step("OK", f"Soul: {soul['name']} | {soul['role']}")
        boot["soul"] = soul
    except Exception as e:
        print_step("WARN", f"Soul: {e}")

    try:
        from orchestration.event_bus import connect_all_learning, event_bus
        connect_all_learning()
        print_step("OK", "Learning loop wired (bandit <-> tracker <-> evolver <-> healer)")
        boot["learning_loop"] = "connected"
    except Exception as e:
        print_step("WARN", f"Learning loop: {e}")

    try:
        from orchestration.kairos_daemon import start_kairos
        r = start_kairos()
        print_step("OK", f"KAIROS daemon (idle threshold: {r.get('idle_threshold_seconds', '?')}s)")
        boot["kairos"] = "started"
    except Exception as e:
        print_step("WARN", f"KAIROS: {e}")

    try:
        from features.skill_chains_loader import load_all_chains
        stats = load_all_chains()
        print_step("OK", f"Chains loaded: {stats['total']} total, {stats['cron_registered']} cron, {stats['manual_available']} manual")
        boot["chains"] = stats
    except Exception as e:
        print_step("WARN", f"Chains: {e}")

    try:
        from orchestration.swarm_worker import get_swarm_worker
        w = get_swarm_worker()
        w.start()
        ws = w.get_status()
        print_step("OK", f"Swarm worker (pending: {ws.get('pending_count', 0)})")
        boot["swarm"] = "started"
    except Exception as e:
        print_step("WARN", f"Swarm: {e}")

    try:
        from evolution.nightly_scorer import NightlyScorer
        print_step("OK", "Skill evolver + nightly scorer online")
        boot["evolver"] = "online"
    except Exception as e:
        print_step("WARN", f"Evolver: {e}")

    return boot


def run_active_phase(metrics: LongRunMetrics, cycle: int) -> Dict:
    cat, chain = metrics.next_chain_category()
    print(f"\n  >>> ACTIVE PHASE (cycle {cycle}): {cat}/{chain}", flush=True)

    try:
        from features.skill_chains_loader import execute_chain
        result = execute_chain(chain)
        metrics.record_chain(cat, chain, result)
        status = result.get("status", "error")
        ok = status == "ok"
        print(f"  [{'OK' if ok else 'ERR'}] {chain} -> {status} ({result.get('steps_ok', 0)}/{result.get('steps_total', 0)} steps) in {result.get('duration_seconds', 0)}s", flush=True)
        return result
    except Exception as e:
        metrics.record_error(f"chain_{chain}", str(e))
        print(f"  [FAIL] {chain}: {e}", flush=True)
        return {"status": "error", "error": str(e)}


def run_passive_phase(metrics: LongRunMetrics, cycle: int):
    print(f"\n  >>> PASSIVE PHASE (cycle {cycle}): idle wait for KAIROS + autoDream", flush=True)
    # Don't touch activity — let KAIROS detect idle
    idle_seconds = 90
    print(f"  [WAIT] {idle_seconds}s quiet period...", flush=True)
    time.sleep(idle_seconds)

    # Check what KAIROS did
    try:
        from orchestration.kairos_daemon import kairos_status
        ks = kairos_status()
        print(f"  [KAIROS] runs={ks['total_runs']} triggers={ks['idle_triggers']} idle={ks['is_currently_idle']}", flush=True)
        if ks["total_runs"] > 0:
            print(f"  [KAIROS] Maintenance completed: {ks['last_maintenance']}", flush=True)
    except Exception as e:
        print(f"  [KAIROS] check failed: {e}", flush=True)


def run_healing_phase(metrics: LongRunMetrics, cycle: int):
    print(f"\n  >>> HEALING PHASE (cycle {cycle}): circuit breaker + daemon watchdog", flush=True)

    try:
        from orchestration.runtime_healer import runtime_healer

        # Reset stress_test_skill at start of each phase so circuit can recover
        # (otherwise failures accumulate forever and circuit stays open indefinitely)
        h = runtime_healer._get_health("stress_test_skill")
        with runtime_healer._lock:
            h.failure_count = 0
            h.failures_window.clear()
            h.state = "closed"
            h.opened_at = 0.0

        # Test circuit breaker
        runtime_healer.record_success("long_run_test")
        cb = runtime_healer.circuit_breaker_state("long_run_test")
        print(f"  [CB] long_run_test = {cb['state']} (failures: {cb['failure_count']})", flush=True)

        # Record simulated failures to test circuit opening
        for i in range(3):
            runtime_healer.record_failure("stress_test_skill")
        cb2 = runtime_healer.circuit_breaker_state("stress_test_skill")
        print(f"  [CB] stress_test_skill = {cb2['state']} (failures: {cb2['failure_count']})", flush=True)

        # Check all daemons
        dr = runtime_healer.check_daemons()
        if dr:
            for d in dr:
                print(f"  [WATCHDOG] {d['daemon']}: {d.get('action', 'alive')}", flush=True)

        # Heal from corrections
        healed = runtime_healer.heal_from_corrections()
        if healed:
            print(f"  [HEAL] Deprecated {healed} hopeless skills from corrections", flush=True)

        # Retry logic test
        def test_fn():
            return {"status": "ok", "result": "long_run_retry_ok"}
        retry_r = runtime_healer.execute_with_retry(test_fn, "long_run_retry", max_retries=2, backoff_ms=100)
        print(f"  [RETRY] Result: {retry_r.get('status', '?')}", flush=True)

    except Exception as e:
        metrics.record_error("healing_phase", str(e))
        print(f"  [FAIL] Healing: {e}", flush=True)


def run_learning_phase(metrics: LongRunMetrics, cycle: int):
    print(f"\n  >>> LEARNING PHASE (cycle {cycle}): bandit feed + evolver scoring", flush=True)

    try:
        from brain.autodream import run_autodream
        result = run_autodream(dry_run=False)
        patterns = result.get("session_patterns", {})
        corrections = len(result.get("corrections", []))
        print(f"  [AUTODREAM] sessions={patterns.get('total_sessions', 0)} corrections={corrections}", flush=True)
        print(f"  [AUTODREAM] qdrant={result.get('qdrant_dedup', {}).get('code_kb', {}).get('status', '?')}", flush=True)
        print(f"  [AUTODREAM] neo4j={result.get('neo4j_optimize', {}).get('status', '?')}", flush=True)
        print(f"  [AUTODREAM] knowledge_bank={result.get('knowledge_bank_consolidation', {}).get('status', '?')}", flush=True)
        print(f"  [AUTODREAM] swarm={result.get('swarm_work', {}).get('status', '?')}", flush=True)
        print(f"  [AUTODREAM] repo_inventory={result.get('repo_inventory', {}).get('status', '?')}", flush=True)
    except Exception as e:
        metrics.record_error("learning_phase", str(e))
        print(f"  [FAIL] Learning: {e}", flush=True)

    try:
        from evolution.nightly_scorer import NightlyScorer
        scorer = NightlyScorer()
        score_result = scorer.run_daily_score()
        print(f"  [SCORER] Daily score: {score_result.get('scored', 0)} skills scored", flush=True)
    except Exception as e:
        print(f"  [SCORER] Skipped: {e}", flush=True)


# ─────────────────────────────────────────────────────────────────────
# REPORT PRINTER
# ─────────────────────────────────────────────────────────────────────

def print_final_report(report: Dict):
    print_banner("FINAL PRODUCTIVITY REPORT")
    print(f"  Runtime: {report['elapsed_hours']}h ({report['elapsed_seconds']}s)")
    print(f"  Cycles: {report['total_cycles']} | Chains Executed: {report['total_chain_executions']} | Errors: {report['total_errors']}")
    print(f"  Health Score: {report['health_score']}/100\n")

    print("  -- KAIROS --")
    k = report["kairos"]
    print(f"  Maintenance Runs: {k['total_maintenance_runs']} | Idle Triggers: {k['idle_triggers']} | Running: {k['running']}")

    print("\n  -- AutoDream --")
    a = report["autodream"]
    print(f"  Last Run: {a['last_run']} | Corrections: {a['corrections_found']}")

    print("\n  -- Cron Scheduler --")
    c = report["cron"]
    print(f"  Tasks: {c['tasks_registered']} | Executions: {c['total_executions']} | Running: {c['running']}")

    print("\n  -- Runtime Healer --")
    h = report["healer"]
    print(f"  Circuits Tracked: {h['circuits_tracked']} | Open: {h['open_circuits']} | Heal Events: {h['heal_events_logged']}")

    print("\n  -- Learning Loop --")
    lr = report["learning"]
    print(f"  Bandit Arms: {lr['bandit_arms']} | Reward Sessions: {lr['reward_sessions']} | Skills Tracked: {lr['skills_tracked']}")

    print("\n  -- Chain Execution by Category --")
    by_cat = report["chain_results_by_category"]
    for cat, stats in sorted(by_cat.items()):
        rate = round(stats["ok"] / max(stats["total"], 1) * 100)
        print(f"  {cat:15s} total={stats['total']:2d}  ok={stats['ok']:2d}  failed={stats['failed']:2d}  success_rate={rate}%")

    print("\n  -- Performance --")
    p = report["performance"]
    print(f"  CPU avg: {p['cpu_avg']}% | Memory avg: {p['mem_avg']}% | Memory now: {p['mem_last']}% | Threads: {p['threads_last']}")

    print(f"\n  Report saved to: {REPORT_DIR}/")


# ─────────────────────────────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────────────────────────────

def run_long_test(hours: float = 0.5):
    cycle_duration_s = 120  # ~2 minutes per cycle
    total_cycles = max(1, int((hours * 3600) / cycle_duration_s))

    print_banner(f"LONG-RUN BENCHMARK: {hours}h ({total_cycles} cycles)")
    print(f"  Start: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Phases per cycle: ACTIVE -> PASSIVE -> HEALING -> LEARNING")
    print(f"  Cycle duration: ~{cycle_duration_s}s\n")

    # Boot
    boot = boot_system()
    time.sleep(1)

    metrics = LongRunMetrics()
    phase_order = ["active", "passive", "healing", "learning"]

    try:
        for cycle in range(1, total_cycles + 1):
            cycle_start = time.time()
            phase = phase_order[(cycle - 1) % len(phase_order)]

            if phase == "active":
                run_active_phase(metrics, cycle)
            elif phase == "passive":
                run_passive_phase(metrics, cycle)
            elif phase == "healing":
                run_healing_phase(metrics, cycle)
            elif phase == "learning":
                run_learning_phase(metrics, cycle)

            snap = metrics.snapshot(cycle, phase)
            elapsed = time.time() - cycle_start
            print(f"  [SNAP] Health: {metrics._health_score(snap)}/100 | CPU: {snap['system']['cpu']}% | Mem: {snap['system']['mem']}% | Cycle: {elapsed:.0f}s")

            if cycle < total_cycles:
                remaining = cycle_duration_s - elapsed
                if remaining > 5:
                    print(f"  [SLEEP] {remaining:.0f}s until next cycle...")
                    time.sleep(max(1, remaining - 2))

    except KeyboardInterrupt:
        print("\n  Interrupted by user. Generating partial report...\n")

    report = metrics.generate_report()
    print_final_report(report)
    return report


def show_last_report():
    rp = REPORT_DIR / "report.json"
    if rp.exists():
        report = json.loads(rp.read_text())
        print_final_report(report)
    else:
        print("No report found. Run long_run.py first.")


def main():
    parser = argparse.ArgumentParser(description="Deterministic Brain — Long-Run Benchmark")
    parser.add_argument("--hours", type=float, default=0.5,
                        help="Hours to run (default: 0.5)")
    parser.add_argument("--report-only", action="store_true",
                        help="Print last report and exit")
    args = parser.parse_args()

    if args.report_only:
        show_last_report()
        return

    try:
        run_long_test(hours=args.hours)
    except KeyboardInterrupt:
        print("\nDone.")
    except Exception as e:
        print(f"\nFATAL: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

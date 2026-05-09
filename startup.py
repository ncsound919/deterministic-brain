#!/usr/bin/env python3
"""startup.py — One-command boot for the deterministic brain.

Brings up the full stack in one go:
  1. Loads Tap's .soul.yaml identity
  2. Wires the full learning loop (bandit ↔ tracker ↔ evolver ↔ healer)
  3. Loads cron schedules aligned to EST daily rhythm
  4. Starts KAIROS daemon for idle-time maintenance
  5. Optionally starts FastAPI server

Usage:
    python startup.py              # Boot everything (daemon + cron + server)
    python startup.py --no-server  # Boot daemon + cron only
    python startup.py --status     # Show current system status
    python startup.py --stop       # Graceful shutdown
"""

from __future__ import annotations
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ═══════════════════════════════════════════════════════════════════════
# Health check helpers
# ═══════════════════════════════════════════════════════════════════════

def _check_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


# ═══════════════════════════════════════════════════════════════════════
# Step 1: Soul load
# ═══════════════════════════════════════════════════════════════════════

def load_soul() -> dict:
    print("\n" + "=" * 60)
    print("  DETERMINISTIC BRAIN — BOOT SEQUENCE")
    print("=" * 60)

    try:
        from brain.soul import get_soul, reset_soul
        reset_soul()
        soul = get_soul()
        s = soul.pulse()
        print(f"\n  Soul loaded: {s['name']} | {s['role']}")
        print(f"  Mission: {s['mission']}")
        print(f"  Goals: {s['goals']} | Directives: {s['directives']}")
        print(f"  Sessions: {s['sessions']}")
        return s
    except Exception as e:
        print(f"\n  [WARN] Soul not loaded: {e}")
        return {"name": "Tap", "loaded": False}


# ═══════════════════════════════════════════════════════════════════════
# Step 2: Learning loop
# ═══════════════════════════════════════════════════════════════════════

def connect_learning_loop() -> dict:
    print("\n  --- Learning Loop ---")
    status = {}

    try:
        from orchestration.event_bus import connect_all_learning, event_bus
        connect_all_learning()
        print("  [OK] Full learning loop wired (bandit ↔ tracker ↔ evolver ↔ healer)")
        status["learning_loop"] = "connected"
    except Exception as e:
        print(f"  [WARN] Learning loop partial: {e}")
        status["learning_loop"] = f"partial: {e}"

    try:
        from reasoning.contextual_bandit import get_bandit
        bandit = get_bandit()
        stats = bandit.get_stats()
        print(f"  [OK] Bandit: {stats['total_arms']} arms, {stats['contexts_explored']} contexts")
        status["bandit"] = {"arms": stats["total_arms"], "contexts": stats["contexts_explored"]}
    except Exception:
        status["bandit"] = "not_loaded"

    try:
        from reasoning.policy_engine import get_policy_engine
        pe = get_policy_engine()
        policies = pe.list_policies()
        print(f"  [OK] Policy Engine: {len(policies)} guardrails active")
        status["policies"] = len(policies)
    except Exception:
        status["policies"] = "not_loaded"

    try:
        from evolution.reward_tracker import get_reward_tracker
        rt = get_reward_tracker()
        s = rt.stats()
        print(f"  [OK] Reward Tracker: {s['active_sessions']} sessions, {s['total_conversions']} conversions")
        status["reward_tracker"] = s
    except Exception:
        status["reward_tracker"] = "not_loaded"

    try:
        from evolution.skill_evolver import SkillEvolver
        ev = SkillEvolver()
        stats_list = ev.all_stats()
        print(f"  [OK] Skill Evolver: {len(stats_list)} skills tracked")
        status["evolver"] = f"{len(stats_list)} skills"
    except Exception:
        status["evolver"] = "not_loaded"

    return status


# ═══════════════════════════════════════════════════════════════════════
# Step 3: Cron schedules
# ═══════════════════════════════════════════════════════════════════════

def load_cron_schedule() -> dict:
    print("\n  --- Cron Schedules ---")

    try:
        from features.skill_chains_loader import load_all_chains
        stats = load_all_chains()
        print(f"  [OK] Chains loaded: {stats['total']} total, {stats['cron_registered']} cron, {stats['manual_available']} manual")
        if stats.get("errors"):
            for err in stats["errors"]:
                print(f"  [WARN] {err}")
        return {"tasks_loaded": stats['total'], "scheduler_running": True}
    except Exception as e:
        print(f"  [WARN] Chain loader: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# Step 4: Repo inventory
# ═══════════════════════════════════════════════════════════════════════

def load_repo_inventory() -> dict:
    print("\n  --- Repo Inventory ---")
    status = {}

    try:
        from features.repo_inventory import get_repo_inventory
        inventory = get_repo_inventory()
        stats = inventory.get_stats()

        if stats["total"] == 0:
            print("  [INFO] Inventory empty — running first discovery...")
            result = inventory.discover()
            if result.get("status") == "ok":
                print(f"  [OK] Discovered {result.get('discovered', 0)} repos "
                      f"({result.get('new_repos', 0)} new) "
                      f"across {result.get('accounts', [])}")
                stats = inventory.get_stats()
            else:
                print(f"  [WARN] Discovery: {result.get('reason', result)}")
        else:
            print(f"  [OK] Repo inventory loaded — {stats['total']} repos tracked")
            print(f"       Active: {stats['active']} | Audited: {stats['audited']} "
                  f"| Stars: {stats['total_stars']} | Languages: {len(stats['by_language'])}")

            # Auto-queue un-audited repos
            needing = stats["active"] - stats["audited"] - stats["in_swarm_queue"]
            if needing > 0:
                print(f"       {needing} repos need auditing — auto-queuing...")
                try:
                    q_result = inventory.auto_queue(max_per_run=5)
                    if q_result.get("status") == "ok":
                        print(f"       [OK] Queued {q_result.get('queued', 0)} repos for swarm audit")
                except Exception as e:
                    print(f"       [WARN] Auto-queue: {e}")

        status["repo_inventory"] = stats

    except Exception as e:
        print(f"  [WARN] Repo inventory: {e}")
        status["repo_inventory"] = f"error: {e}"

    return status


# ═══════════════════════════════════════════════════════════════════════
# Step 5: KAIROS daemon
# ═══════════════════════════════════════════════════════════════════════

def load_credentials() -> dict:
    print("\n  --- Credential Vault ---")
    status = {}

    try:
        from config.credentials import get_credential_vault
        vault = get_credential_vault()
        stats = vault.stats()
        if not vault.is_empty():
            vault.sync_to_env()
            print(f"  [OK] Credential vault loaded — {stats['categories']} categories, {stats['total_keys']} keys")
            for cat in stats["categories_list"]:
                keys = vault.list_keys(cat)
                print(f"       {cat}: {len(keys)} keys ({', '.join(keys)})")
            status["credential_vault"] = stats
        else:
            print("  [WARN] Credential vault is empty — run 'python config/credentials.py --init'")
            status["credential_vault"] = "empty"
    except Exception as e:
        print(f"  [WARN] Credential vault: {e}")
        status["credential_vault"] = f"error: {e}"

    return status


def start_daemons() -> dict:
    print("\n  --- Daemons ---")
    status = {}

    try:
        from orchestration.kairos_daemon import start_kairos, kairos_status
        result = start_kairos()
        print(f"  [OK] KAIROS daemon started (idle threshold: {result.get('idle_threshold_seconds', 0)}s)")
        status["kairos"] = "running"

        try:
            from features.autonomy import get_autonomy
            autonomy = get_autonomy()
            print("  [OK] Autonomy scheduler connected to KAIROS")
            status["autonomy"] = "connected"
        except Exception:
            status["autonomy"] = "not_loaded"

    except Exception as e:
        print(f"  [WARN] KAIROS: {e}")
        status["kairos"] = f"error: {e}"

    try:
        from orchestration.swarm_worker import get_swarm_worker
        worker = get_swarm_worker()
        worker.start()
        ws = worker.get_status()
        print(f"  [OK] Swarm worker started — queue: {ws.get('pending_count', 0)} pending")
        status["swarm_worker"] = "running"
    except Exception as e:
        print(f"  [WARN] Swarm worker: {e}")
        status["swarm_worker"] = f"error: {e}"

    return status


# ═══════════════════════════════════════════════════════════════════════
# Step 6: FastAPI server (optional)
# ═══════════════════════════════════════════════════════════════════════

def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    print(f"\n  --- API Server ---")
    try:
        import uvicorn
        print(f"  [OK] Starting FastAPI on http://{host}:{port}")
        print(f"  [OK] Dashboard: http://localhost:{port}")
        print(f"  [OK] API Docs:  http://localhost:{port}/docs")
        uvicorn.run("api.server:app", host=host, port=port, reload=False, log_level="warning")
    except Exception as e:
        print(f"  [ERROR] Server failed: {e}")


# ═══════════════════════════════════════════════════════════════════════
# Daily rhythm
# ═══════════════════════════════════════════════════════════════════════

def print_rhythm():
    print(f"""
  {"=" * 56}
    DAILY RHYTHM (EST — Tap's schedule)
  {"=" * 56}

    03:00  learning-consolidation (bandit evolve, autodream)
    07:00  morning-kickstart (news, market, agent health)
    09:00  content-publish (morning social)
    10:00  marketing-autopilot (SEO, AEO)
    12:00  content-publish (midday social)
    16:00  content-publish (afternoon social)
    20:00  autodream (knowledge bank consolidation)
    22:00  midnight-deep-work (heavy compute)
    02:00  repo-health (Sunday only)
    08:00  weekly-report (Monday only)

    agent-health-check: every 30 minutes
    ncsound-branding: Wed & Sat 12 PM

    6-7am   Tap wakes up
    12pm    Lunch break
    4pm     Kids time
    7pm     Wind down
    10pm-1am Peak coding window

  {"=" * 56}
""")


# ═══════════════════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════════════════

def show_status():
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
    }

    try:
        from brain.soul import get_soul
        result["soul"] = get_soul().summary()
    except Exception as e:
        result["soul"] = f"error: {e}"

    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        result["scheduler"] = {
            "running": s.is_running(),
            "tasks": len(s.list_tasks()),
        }
    except Exception as e:
        result["scheduler"] = f"error: {e}"

    try:
        from orchestration.kairos_daemon import kairos_status
        result["kairos"] = kairos_status()
    except Exception as e:
        result["kairos"] = f"error: {e}"

    try:
        from reasoning.contextual_bandit import get_bandit
        result["bandit"] = get_bandit().get_stats()
    except Exception:
        result["bandit"] = "not_loaded"

    try:
        from evolution.reward_tracker import get_reward_tracker
        result["reward_tracker"] = get_reward_tracker().stats()
    except Exception:
        result["reward_tracker"] = "not_loaded"

    print(json.dumps(result, indent=2, default=str))


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic Brain — Startup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--no-server", action="store_true", help="Skip API server")
    parser.add_argument("--host", default="0.0.0.0", help="API host")
    parser.add_argument("--port", type=int, default=8000, help="API port")
    parser.add_argument("--status", action="store_true", help="Show system status and exit")
    parser.add_argument("--stop", action="store_true", help="Stop daemons and exit")
    parser.add_argument("--no-cron", action="store_true", help="Skip cron scheduler")
    parser.add_argument("--no-daemon", action="store_true", help="Skip KAIROS daemon")

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.stop:
        try:
            from orchestration.kairos_daemon import stop_kairos
            stop_kairos()
            print("Daemons stopped.")
        except Exception as e:
            print(f"Stop error: {e}")
        try:
            from features.scheduler import get_scheduler
            get_scheduler().stop()
            print("Scheduler stopped.")
        except Exception:
            pass
        return

    # Boot sequence
    load_soul()
    connect_learning_loop()
    load_credentials()
    load_repo_inventory()

    if not args.no_cron:
        load_cron_schedule()

    if not args.no_daemon:
        start_daemons()

    print_rhythm()

    if args.no_server:
        print("  Running in headless mode. Press Ctrl+C to stop.\n")
        try:
            signal.pause()
        except AttributeError:
            while True:
                time.sleep(60)
    else:
        # Register signal handler for graceful shutdown
        def _shutdown(sig, frame):
            print("\nShutting down...")
            try:
                from orchestration.swarm_worker import get_swarm_worker
                get_swarm_worker().stop()
            except Exception:
                pass
            try:
                from orchestration.kairos_daemon import stop_kairos
                stop_kairos()
            except Exception:
                pass
            try:
                from features.scheduler import get_scheduler
                get_scheduler().stop()
            except Exception:
                pass
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        start_server(args.host, args.port)


if __name__ == "__main__":
    main()

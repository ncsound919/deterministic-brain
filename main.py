#!/usr/bin/env python3
"""CLI entry point for the Deterministic Brain.

Usage:
  python main.py "create a react component named UserCard with props name, email"
  python main.py --bundle scaffold-rest-api --inputs '{"resource": "User"}'
  python main.py --bundle audit-repo --inputs '{"repo_path": "./my-project"}'
  python main.py --skills
  python main.py --serve
"""
from __future__ import annotations
import argparse
import json
import time
import sys
import signal
import threading


# Global shutdown flag — set by SIGTERM/SIGINT, checked before new work
_shutdown_requested = threading.Event()


def _signal_handler(sig, frame):
    """Signal handler for graceful shutdown — waits for in-flight skills."""
    if _shutdown_requested.is_set():
        return
    print("\nShutdown requested — waiting for in-flight skills to complete...")
    _shutdown_requested.set()


def is_shutdown_requested() -> bool:
    """Check if shutdown has been requested (for in-flight skill checks)."""
    return _shutdown_requested.is_set()


def main() -> None:
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    parser = argparse.ArgumentParser(
        description="Deterministic Coding Agent — zero LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query",   nargs="?",  help="Natural language task")
    parser.add_argument("--bundle", "-b",       help="Fire a swarm bundle by name")
    parser.add_argument("--inputs", "-i",       help="JSON inputs for bundle", default="{}")
    parser.add_argument("--skills",             action="store_true", help="List indexed skills")
    parser.add_argument("--serve",              action="store_true", help="Start FastAPI server")
    parser.add_argument("--repl",               action="store_true", help="Start interactive debug REPL")
    parser.add_argument("--autodream",          action="store_true", help="Run autoDream memory consolidation")
    parser.add_argument("--kairos",             action="store_true", help="Start KAIROS daemon mode")
    parser.add_argument("--kairos-status",     action="store_true", help="Show KAIROS daemon status")
    parser.add_argument("--health",             action="store_true", help="Run startup health check")
    parser.add_argument("--verbose", "-v",      action="store_true")
    args = parser.parse_args()

    if args.repl:
        from cli.brain_repl import main as repl_main
        import sys
        sys.argv = [sys.argv[0]]  # reset to avoid argparse conflicts in repl
        repl_main()
        return

    if args.serve:
        import uvicorn
        import os
        port = int(os.environ.get("API_PORT", 8000))
        distributed = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")
        workers = int(os.environ.get("UVICORN_WORKERS", "0"))
        if workers > 1 and not distributed:
            import logging
            logging.warning("Multiple uvicorn workers require DISTRIBUTED_MODE=1. Falling back to 1 worker.")
            workers = 1
        print(f"Starting Deterministic Brain API on http://0.0.0.0:{port}" +
              (f" with {workers} workers" if workers > 1 else ""))
        uvicorn.run(
            "api.server:app",
            host="0.0.0.0",
            port=port,
            workers=workers or None,
            reload=False,
        )
        return

    if args.skills:
        from orchestration.skill_registry import get_skill_registry
        registry = get_skill_registry()
        registry.discover()
        for skill in registry.list_all():
            print(f"  {skill.skill_id:40s}  {skill.skill_path}")
        return

    if args.bundle:
        from orchestration.swarm_dispatcher import SwarmDispatcher
        swarm  = SwarmDispatcher()
        inputs = json.loads(args.inputs)
        t0     = time.perf_counter()
        result = swarm.dispatch(args.bundle, inputs)
        ms     = round((time.perf_counter() - t0) * 1000)
        print(f"[{ms}ms] bundle={args.bundle}")
        print(json.dumps(result, indent=2, default=str))
        return

    if args.query:
        if _shutdown_requested.is_set():
            print("Shutdown in progress — rejecting new work.")
            sys.exit(1)
        from orchestration.dca_engine import DeterministicCodingAgent
        agent  = DeterministicCodingAgent()
        agent.register_shutdown_check(is_shutdown_requested)
        t0     = time.perf_counter()
        result = agent.handle(args.query)
        ms     = round((time.perf_counter() - t0) * 1000)
        print(f"[{ms}ms]")
        if args.verbose:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Status : {result.get('status')}")
            print(f"Output : {result.get('final_output')}")
        if _shutdown_requested.is_set():
            print("Graceful shutdown complete.")
        return

    if args.autodream:
        from brain.autodream import run_autodream
        print("Running autoDream memory consolidation...")
        results = run_autodream(dry_run=False)
        print(json.dumps(results, indent=2, default=str))
        return

    if args.kairos:
        from orchestration.kairos_daemon import start_kairos
        print("Starting KAIROS daemon (Ctrl+C to stop)...")
        shutdown_event = threading.Event()

        def signal_handler(sig, frame):
            print("\nStopping KAIROS daemon...")
            from orchestration.kairos_daemon import stop_kairos
            stop_kairos()
            shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        result = start_kairos()
        print(f"Daemon started: {json.dumps(result, indent=2)}")
        try:
            shutdown_event.wait()
        except KeyboardInterrupt:
            shutdown_event.set()
        return

    if args.health:
        from brain.health_check import run_health_check, print_health_report
        result = run_health_check()
        print_health_report(result)
        sys.exit(0 if result.passed else 1)

    if args.kairos_status:
        from orchestration.kairos_daemon import kairos_status
        result = kairos_status()
        print(json.dumps(result, indent=2, default=str))
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()

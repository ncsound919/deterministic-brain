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
import sys
import time


def main() -> None:
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
    parser.add_argument("--verbose", "-v",      action="store_true")
    args = parser.parse_args()

    if args.serve:
        import uvicorn
        print("Starting Deterministic Brain API on http://0.0.0.0:8000")
        uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
        return

    if args.skills:
        from orchestration.dca_engine import DeterministicCodingAgent
        agent = DeterministicCodingAgent()
        for name, path in agent.skills.items():
            print(f"  {name:40s}  {path}")
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
        from orchestration.dca_engine import DeterministicCodingAgent
        agent  = DeterministicCodingAgent()
        t0     = time.perf_counter()
        result = agent.handle(args.query)
        ms     = round((time.perf_counter() - t0) * 1000)
        print(f"[{ms}ms]")
        if args.verbose:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Status : {result.get('status')}")
            print(f"Output : {result.get('final_output')}")
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()

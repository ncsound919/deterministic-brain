#!/usr/bin/env python3
"""CLI entry point for the Deterministic Brain.

Usage:
    python main.py "your query here"
    python main.py --lane coding "write a binary search"
    python main.py --trace <session_id>
    python main.py --sessions
    python main.py --config
    python main.py --serve        # starts FastAPI server
    python main.py --demo         # runs built-in demo queries
"""
from __future__ import annotations
import argparse
import json
import sys
import time


def _print_result(result: dict, verbose: bool = False) -> None:
    print(f"\n{'='*60}")
    print(f"Session : {result.get('session_id', '')}")
    print(f"Lane    : {result.get('lane', '')}")
    print(f"Status  : {result.get('status', '')}")
    print(f"Mode    : {result.get('output_mode', '')}")
    print(f"Conf    : {result.get('confidence', 0):.2f}")
    print(f"{'='*60}")
    print(result.get('final_output', ''))
    if verbose:
        print(f"\n--- Verification ---")
        for v in result.get('verification_results', []):
            print(f"  [{v.get('stage')}] passed={v.get('passed')} "
                  f"score={v.get('soft_score', 'n/a')} reason={v.get('reason')}")
        print(f"\n--- History ---")
        for h in result.get('history', []):
            print(f"  {h}")
    print()


_DEMO_QUERIES = [
    ('coding',        'Write python code for a deterministic router'),
    ('business_logic','Create a business rule approval policy for budget requests'),
    ('agent_brain',   'Use browser agent to navigate to the dashboard and extract metrics'),
    ('tool_calling',  'Call a tool to validate data schema and run qdrant search'),
    ('cross_domain',  'Analyze cross-domain trends in AI and climate data'),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Lane-First Deterministic Brain CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('query', nargs='?', help='Query to run')
    parser.add_argument('--lane', '-l', help='Override lane selection')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show full trace')
    parser.add_argument('--trace', metavar='SESSION_ID', help='Print trace for session')
    parser.add_argument('--sessions', action='store_true', help='List all sessions')
    parser.add_argument('--config', action='store_true', help='Print current config')
    parser.add_argument('--serve', action='store_true', help='Start FastAPI server')
    parser.add_argument('--demo', action='store_true', help='Run all demo queries')
    args = parser.parse_args()

    if args.config:
        from config import cfg
        print(json.dumps(cfg.summary(), indent=2))
        return

    if args.sessions:
        from tools.tracing import list_sessions
        sessions = list_sessions()
        if sessions:
            print('\n'.join(sessions))
        else:
            print('No sessions found.')
        return

    if args.trace:
        from tools.tracing import get_trace
        trace = get_trace(args.trace)
        print(json.dumps(trace, indent=2, default=str))
        return

    if args.serve:
        import uvicorn
        from config import cfg
        print(f'Starting server on {cfg.api_host}:{cfg.api_port}')
        uvicorn.run('api.server:app', host=cfg.api_host, port=cfg.api_port, reload=False)
        return

    from orchestration.langgraph_app import build_app
    brain = build_app()

    if args.demo:
        print('Running demo queries...\n')
        for _, query in _DEMO_QUERIES:
            t0 = time.perf_counter()
            result = brain.run(query)
            elapsed = round((time.perf_counter() - t0) * 1000)
            print(f'[{elapsed}ms] Q: {query[:60]}')
            _print_result(result, verbose=args.verbose)
        return

    if not args.query:
        parser.print_help()
        sys.exit(1)

    t0 = time.perf_counter()
    result = brain.run(args.query, lane_override=args.lane)
    elapsed = round((time.perf_counter() - t0) * 1000)
    print(f'[{elapsed}ms]')
    _print_result(result, verbose=args.verbose)


if __name__ == '__main__':
    main()

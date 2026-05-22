#!/usr/bin/env python3
"""Interactive Debug REPL for Deterministic Brain.

Usage:
    python -m cli.brain_repl
    python main.py --repl

Commands:
    run <query>       — Execute a task through DCAEngine
    inspect <id>      — Inspect session / skill state
    status            — Dump healer + metrics summary
    heal              — Trigger daemon health check
    constraints       — List active Z3 learned constraints
    watch on|off      — Toggle hot-reload skill watcher
    recover <skill>   — Reset circuit breaker for a skill
    exit / quit       — Exit REPL
"""
from __future__ import annotations
import cmd
import json
import sys
import shlex
import time


class BrainREPL(cmd.Cmd):
    intro = "\n  Deterministic Brain Debug REPL\n  Type help or ? for commands.\n"
    prompt = "(brain) "

    def __init__(self, agent=None):
        super().__init__()
        self._agent = agent
        self._healer = None
        self._metrics = None
        self._skill_registry = None
        self._lazy_imports()

    def _lazy_imports(self):
        try:
            from orchestration.runtime_healer import runtime_healer
            self._healer = runtime_healer
        except Exception:
            pass
        try:
            from tools.metrics import get_metrics
            self._metrics = get_metrics()
        except Exception:
            pass
        try:
            from orchestration.skill_registry import get_skill_registry
            self._skill_registry = get_skill_registry()
        except Exception:
            pass

    # ── Commands ─────────────────────────────────────────────────

    def do_run(self, arg):
        """run <query> — Execute a task through DCAEngine."""
        if not arg:
            print("Usage: run <query>")
            return
        if self._agent is None:
            try:
                from orchestration.dca_engine import DeterministicCodingAgent
                self._agent = DeterministicCodingAgent()
            except Exception as e:
                print(f"Error creating agent: {e}")
                return
        t0 = time.perf_counter()
        try:
            result = self._agent.handle(arg)
            ms = round((time.perf_counter() - t0) * 1000)
            print(f"\n[{ms}ms] status={result.get('status')}")
            if result.get("final_output"):
                out = result["final_output"]
                if isinstance(out, dict):
                    print(json.dumps(out, indent=2, default=str)[:2000])
                else:
                    print(str(out)[:2000])
            else:
                print(json.dumps(result, indent=2, default=str)[:2000])
        except Exception as e:
            print(f"Error: {e}")

    def do_inspect(self, arg):
        """inspect <session_id> — Inspect persisted session state."""
        if not arg:
            print("Usage: inspect <session_id>")
            return
        try:
            from brain.state_manager import get_state_manager
            sm = get_state_manager()
            session = sm.load(arg.strip())
            if session:
                print(json.dumps(session.to_dict() if hasattr(session, 'to_dict') else session,
                                 indent=2, default=str)[:3000])
            else:
                print(f"No session found: {arg}")
        except Exception as e:
            print(f"Error loading session: {e}")

    def do_status(self, arg):
        """status — Dump healer + metrics summary."""
        print("\n=== Healer ===")
        if self._healer:
            snap = self._healer.health_snapshot()
            print(f"  Skills tracked:    {snap['skills_tracked']}")
            print(f"  Circuits open:     {snap['circuits_open']}")
            print(f"  Circuits half-open:{snap['circuits_half_open']}")
            print(f"  Daemons watched:   {snap['daemons_watched']}")
            print(f"  Learned constraints: {snap['learned_constraints']}")
            for s in snap['skills']:
                if s['state'] != 'closed':
                    print(f"    {s['skill_id']:30s} state={s['state']:10s} "
                          f"fails={s['failure_count']} ema={s['failure_rate_ema']}")
            print()
            print("  Recent events:")
            for ev in snap['recent_events'][-5:]:
                ts = time.strftime('%H:%M:%S', time.localtime(ev['ts']))
                print(f"    [{ts}] {ev['event']} {ev['data']}")
        else:
            print("  (healer not available)")

        print("\n=== Metrics ===")
        if self._metrics:
            snap = self._metrics.snapshot()
            print(f"  Total requests: {snap['total_requests']}")
            print(f"  Cache hit ratio: {snap['cache']['hit_ratio']}")
            print(f"  SQLite avg ms:   {snap['sqlite']['avg_ms']}")
            print(f"  Uptime:          {snap['uptime_str']}")
        else:
            print("  (metrics not available)")

    def do_heal(self, arg):
        """heal — Trigger daemon health check and auto-recovery."""
        if self._healer:
            results = self._healer.check_daemons()
            if results:
                for r in results:
                    print(f"  {r['daemon']}: {r['action']}")
            else:
                print("  All daemons healthy.")
            # Auto-recover open circuits
            recovered = self._healer.recover_all()
            if recovered:
                print(f"  Recovered {len(recovered)} circuits.")
        else:
            print("  Healer not available.")

    def do_constraints(self, arg):
        """constraints — List active learned constraints from healer."""
        if self._healer:
            cons = self._healer.get_learned_constraints()
            if cons:
                print(f"\n  Learned constraints ({len(cons)}):")
                for i, c in enumerate(cons, 1):
                    print(f"  {i}. skill={c.get('skill_id','?')} "
                          f"pattern='{c.get('pattern','')[:60]}' "
                          f"failures={c.get('failure_count',0)}")
            else:
                print("  No learned constraints.")
        else:
            print("  Healer not available.")

    def do_recover(self, arg):
        """recover <skill_id> — Reset circuit breaker for a specific skill."""
        if not arg:
            print("Usage: recover <skill_id>")
            return
        if self._healer:
            result = self._healer.recover_skill(arg.strip())
            print(f"  {result['status']}: {result['skill_id']}")
        else:
            print("  Healer not available.")

    def do_watch(self, arg):
        """watch on|off — Toggle hot-reload skill watcher."""
        if not arg:
            print("Usage: watch on|off")
            return
        if self._skill_registry:
            if arg.strip().lower() in ("on", "1", "true"):
                self._skill_registry.enable_watch()
                print("  Skill watcher enabled.")
            else:
                self._skill_registry.disable_watch()
                print("  Skill watcher disabled.")
        else:
            print("  Skill registry not available.")

    def do_replay(self, arg):
        """replay <session_id> or replay --step <session_id> or replay --list"""
        if not arg:
            print("Usage: replay <session_id> | replay --step <session_id> | replay --list")
            return

        parts = shlex.split(arg)

        if "--list" in parts:
            try:
                from orchestration.session_replay import get_replay_engine
                engine = get_replay_engine()
                sessions = engine.list_sessions(20)
                if not sessions:
                    print("  No replayable sessions found.")
                    return
                print(f"\n  Replayable sessions ({len(sessions)}):")
                for s in sessions:
                    print(f"    {s['session_id']:20s} {s['node_sequence'][0]:15s}"
                          f" -> {s['outcome'] or '?'}  ({s['duration_s']}s, {s['nodes_visited']} nodes)")
            except Exception as e:
                print(f"  Error listing sessions: {e}")
            return

        step_mode = "--step" in parts
        session_id = [p for p in parts if p != "--step"][0] if not step_mode else (
            [p for p in parts if p != "--step"][0]
        )

        if not session_id:
            print("  Error: session_id required")
            return

        try:
            from orchestration.session_replay import get_replay_engine
            engine = get_replay_engine()

            if step_mode:
                print(f"\n  Stepping through session {session_id}...\n")
                for node_data in engine.replay(session_id, step=True):
                    print(f"  [{node_data['node']}]")
                    if node_data.get("state"):
                        for k, v in node_data["state"].items():
                            if k == "final_output_preview":
                                print(f"    {k}: {str(v)[:100]}")
                            elif k == "history":
                                print(f"    {k}: {len(v)} entries")
                            elif not isinstance(v, (dict, list)):
                                print(f"    {k}: {v}")
                    if node_data.get("delta"):
                        important_deltas = {k: v for k, v in node_data["delta"].items()
                                            if k in ("status", "confidence", "chosen_skill")}
                        if important_deltas:
                            print(f"    changes: {important_deltas}")
                    print()
            else:
                session = engine.capture_session(session_id)
                if session:
                    desc = engine.describe(session)
                    print(f"\n  Session: {desc['session_id']}")
                    print(f"  Duration: {desc['duration_s']}s")
                    print(f"  Nodes: {desc['nodes_visited']} -> {' -> '.join(desc['node_sequence'])}")
                    print(f"  Outcome: {desc['outcome']}")
                    print(f"  Start: {desc['start_time']}  End: {desc['end_time']}")
                    print()
                    for node_data in engine.replay(session_id, step=False):
                        print(f"  [{node_data['node']}]")
                        for k, v in node_data.get("state", {}).items():
                            if k == "final_output_preview":
                                print(f"    {k}: {str(v)[:100]}")
                            elif k == "history":
                                print(f"    {k}: {len(v)} entries")
                            elif not isinstance(v, (dict, list)):
                                print(f"    {k}: {v}")
                        print()
                else:
                    print(f"  No replay data found for session: {session_id}")
        except Exception as e:
            print(f"  Error: {e}")

    def do_exit(self, arg):
        """exit — Exit the REPL."""
        print("Goodbye.")
        return True

    def do_quit(self, arg):
        """quit — Exit the REPL."""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Ctrl-D to exit."""
        print()
        return True

    # ── Tab completion ───────────────────────────────────────────

    def completenames(self, text, *ignored):
        """Return command names matching text, ensuring 'help' is always offered."""
        d = {}
        for cmd_name in self.get_names():
            if cmd_name.startswith("do_"):
                d[cmd_name[3:]] = 1
        return [c for c in d if c.startswith(text) or (text == "help" and c == "help")]

    def default(self, line):
        print(f"Unknown command: {line}. Type help or ? for commands.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Brain Debug REPL")
    parser.add_argument("--command", "-c", help="Run a single command and exit")
    args = parser.parse_args()

    repl = BrainREPL()

    if args.command:
        repl.onecmd(args.command)
    else:
        try:
            import readline
        except ImportError:
            pass
        repl.cmdloop()


if __name__ == "__main__":
    main()

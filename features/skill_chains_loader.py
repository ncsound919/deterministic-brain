#!/usr/bin/env python3
"""
Skill Chains Loader — Bridges skill_chains.yaml to the APScheduler and DCA engine.

This file was the missing piece: skill_chains.yaml was never loaded by any Python code.
Now chains are parsed, cron chains are registered with the scheduler, and manual chains
are executable via API.

Usage:
    from features.skill_chains_loader import load_all_chains, execute_chain
    
    # On boot: register all cron chains with scheduler
    load_all_chains()
    
    # Execute a manual chain
    result = execute_chain("social-pulse")
"""

from __future__ import annotations
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

CHAIN_RESULTS: Dict[str, List[Dict]] = {}  # Memory store for chain execution results


def _load_yaml() -> Dict:
    """Parse skill_chains.yaml."""
    path = Path("skill_chains.yaml")
    if not path.exists():
        logger.warning("skill_chains.yaml not found")
        return {"chains": {}}
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _execute_skill(skill_name: str, inputs: Dict = None) -> Dict:
    """Execute a single skill via the DCA engine."""
    try:
        from orchestration.dca_engine import DeterministicCodingAgent
        agent = DeterministicCodingAgent()
        query = skill_name
        if inputs:
            extra = " ".join(f"{k}={v}" for k, v in inputs.items() if v)
            if extra:
                query = f"{skill_name} {extra}"
        result = agent.handle(query)
        return {"status": result.get("status", "unknown"), "output": result}
    except Exception as e:
        logger.error(f"Skill execution failed: {skill_name} - {e}")
        return {"status": "error", "error": str(e)}


def _execute_steps(steps: List[Dict]) -> List[Dict]:
    """Execute chain steps, handling parallel execution."""
    import concurrent.futures
    results = []
    parallel_group: List[Dict] = []

    for step in steps:
        if step.get("parallel"):
            parallel_group.append(step)
        else:
            # Flush any pending parallel group
            if parallel_group:
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(parallel_group)) as ex:
                    futures = {ex.submit(_execute_skill, s["skill"], s.get("inputs")): s for s in parallel_group}
                    for f in concurrent.futures.as_completed(futures):
                        results.append(f.result())
                parallel_group = []

            # Execute sequential step
            results.append(_execute_skill(step["skill"], step.get("inputs")))

    # Flush remaining parallel group
    if parallel_group:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(parallel_group)) as ex:
            futures = {ex.submit(_execute_skill, s["skill"], s.get("inputs")): s for s in parallel_group}
            for f in concurrent.futures.as_completed(futures):
                results.append(f.result())

    return results


def execute_chain(chain_name: str, dry_run: bool = False) -> Dict:
    """Execute a named chain from skill_chains.yaml. Callable from API/UI."""
    data = _load_yaml()
    chains = data.get("chains", {})

    if chain_name not in chains:
        return {"status": "error", "error": f"Chain '{chain_name}' not found"}

    chain = chains[chain_name]
    steps = chain.get("steps", [])
    post_steps = chain.get("post", [])
    description = chain.get("description", "")

    if not steps:
        return {"status": "error", "error": f"Chain '{chain_name}' has no steps"}

    if dry_run:
        return {"status": "dry_run", "chain": chain_name, "description": description,
                "steps": [{"skill": s["skill"], "inputs": s.get("inputs", {})} for s in steps],
                "post": [{"skill": p.get("skill"), "call": p.get("call")} for p in post_steps]}

    start_time = time.time()
    logger.info(f"Executing chain: {chain_name} ({len(steps)} steps)")

    # Execute main steps
    step_results = _execute_steps(steps)

    # Execute post-steps
    post_results = []
    all_ok = all(r.get("status") == "ok" for r in step_results)

    for post in post_steps:
        condition = post.get("condition", "always")
        if condition == "on_success" and not all_ok:
            continue

        if post.get("skill"):
            post_results.append(_execute_skill(post["skill"], post.get("inputs")))
        elif post.get("call"):
            # Direct function call: e.g., "reward_tracker.stats"
            try:
                mod_func = post["call"]
                parts = mod_func.rsplit(".", 1)
                if len(parts) == 2:
                    mod = __import__(parts[0], fromlist=[parts[1]])
                    fn = getattr(mod, parts[1])
                    result = fn()
                    post_results.append({"status": "ok", "call": mod_func, "output": str(result)[:500]})
                else:
                    post_results.append({"status": "error", "call": mod_func, "error": "Invalid call format"})
            except Exception as e:
                post_results.append({"status": "error", "call": post["call"], "error": str(e)})

    duration = round(time.time() - start_time, 2)

    result = {
        "chain": chain_name,
        "description": description,
        "status": "ok" if all_ok else "partial",
        "duration_seconds": duration,
        "steps_total": len(steps),
        "steps_ok": sum(1 for r in step_results if r.get("status") == "ok"),
        "steps_failed": sum(1 for r in step_results if r.get("status") != "ok"),
        "step_results": step_results,
        "post_results": post_results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Store result
    if chain_name not in CHAIN_RESULTS:
        CHAIN_RESULTS[chain_name] = []
    CHAIN_RESULTS[chain_name].append(result)
    if len(CHAIN_RESULTS[chain_name]) > 50:
        CHAIN_RESULTS[chain_name] = CHAIN_RESULTS[chain_name][-50:]

    logger.info(f"Chain '{chain_name}' completed in {duration}s ({result['steps_ok']}/{result['steps_total']} OK)")
    return result


def load_all_chains() -> Dict:
    """Parse skill_chains.yaml and register cron chains with the scheduler.

    Returns stats dict with counts.
    """
    data = _load_yaml()
    chains = data.get("chains", {})

    stats = {"total": len(chains), "cron_registered": 0, "manual_available": 0, "errors": []}

    try:
        from features.scheduler import get_scheduler, TaskDefinition
        scheduler = get_scheduler()

        # Wire the executor: when scheduler fires, delegate to execute_chain()
        def scheduler_executor(skill_name: str, inputs: Dict) -> Dict:
            return execute_chain(skill_name)

        scheduler.set_executor(scheduler_executor)

        for name, chain in chains.items():
            trigger = chain.get("trigger", "manual")

            if trigger == "cron":
                cron_expr = chain.get("cron")
                if not cron_expr:
                    stats["errors"].append(f"{name}: cron trigger but no cron expression")
                    continue

                # For cron chains, the "skill" is the chain name itself
                task = TaskDefinition(
                    name=name,
                    skill=name,  # Chain name IS the skill name for the scheduler
                    trigger_type="cron",
                    cron_expr=cron_expr,
                    inputs=chain.get("steps", [])[0].get("inputs", {}) if chain.get("steps") else {},
                    enabled=True,
                )
                scheduler.add_task(task)
                stats["cron_registered"] += 1
                logger.info(f"Registered cron chain: {name} ({cron_expr})")
            else:
                stats["manual_available"] += 1

        if not scheduler.is_running():
            scheduler.start()
            logger.info("Scheduler auto-started by chain loader")

        logger.info(f"Chain loader: {stats['cron_registered']} cron, {stats['manual_available']} manual chains loaded")

    except Exception as e:
        stats["errors"].append(f"Loader failed: {e}")
        logger.error(f"Chain loader failed: {e}")

    return stats


def get_chain_status(chain_name: str = None) -> Dict:
    """Get chain definitions and execution history."""
    data = _load_yaml()
    chains = data.get("chains", {})

    if chain_name:
        chain = chains.get(chain_name)
        if not chain:
            return {"error": f"Chain '{chain_name}' not found"}
        history = CHAIN_RESULTS.get(chain_name, [])
        return {
            "name": chain_name,
            "description": chain.get("description", ""),
            "trigger": chain.get("trigger", "manual"),
            "cron": chain.get("cron"),
            "step_count": len(chain.get("steps", [])),
            "steps": [s["skill"] for s in chain.get("steps", [])],
            "executions": len(history),
            "last_execution": history[-1] if history else None,
        }

    # List all chains
    all_chains = {}
    for name, chain in chains.items():
        history = CHAIN_RESULTS.get(name, [])
        all_chains[name] = {
            "description": chain.get("description", ""),
            "trigger": chain.get("trigger", "manual"),
            "cron": chain.get("cron"),
            "step_count": len(chain.get("steps", [])),
            "executions": len(history),
            "last_run": history[-1]["timestamp"] if history else None,
            "last_status": history[-1]["status"] if history else None,
        }
    return {"chains": all_chains, "total": len(all_chains)}

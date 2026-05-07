from __future__ import annotations
"""
COORDINATOR_MODE — Multi-agent swarm coordinator.

Breaks a complex top-level query into sub-tasks, dispatches each sub-task
to a separate brain instance in a thread pool, collects results, and
merges them into a final synthesis using the cross_domain lane.
"""
import concurrent.futures
import threading
from datetime import datetime
from tools.llm.router import chat
from tools.tracing import log_event

_DECOMPOSE_SYSTEM = (
    'You are a task decomposition expert. '
    'Break the given complex query into 2-5 independent sub-tasks that can be solved in parallel. '
    'Return a JSON array of strings: ["sub-task 1", "sub-task 2", ...]'
)

_MERGE_SYSTEM = (
    'You are a synthesis expert. '
    'Given a set of sub-task results, merge them into a single coherent final answer. '
    'Be concise, structured, and highlight the most important insights.'
)


def decompose(query: str) -> list[str]:
    import json
    raw = chat(system=_DECOMPOSE_SYSTEM, user=f'Query: {query}', lane='cross_domain', max_tokens=512)
    try:
        clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        tasks = json.loads(clean)
        if isinstance(tasks, list):
            return [str(t) for t in tasks[:5]]
    except Exception:
        pass
    return [query]  # fallback: single task


def _run_subtask(sub_query: str, index: int) -> dict:
    from orchestration.langgraph_app import build_app
    brain = build_app()
    result = brain.run(sub_query)
    return {
        'index': index,
        'sub_query': sub_query,
        'lane': result.get('lane', ''),
        'output': result.get('final_output', ''),
        'confidence': result.get('confidence', 0.0),
    }


def coordinate(query: str, max_workers: int = 4) -> dict:
    """Decompose query, run sub-tasks in parallel, merge results."""
    ts_start = datetime.utcnow().isoformat()
    sub_tasks = decompose(query)
    log_event('coordinator_start', {'query': query, 'sub_tasks': sub_tasks})

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_subtask, t, i): i for i, t in enumerate(sub_tasks)}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({'index': futures[future], 'error': str(exc)})

    results.sort(key=lambda r: r.get('index', 0))
    results_text = '\n\n'.join(
        f'Sub-task {r["index"]+1}: {r.get("sub_query", "")}\nResult: {r.get("output", r.get("error", ""))[:400]}'
        for r in results
    )
    merged = chat(
        system=_MERGE_SYSTEM,
        user=f'Original query: {query}\n\nSub-task results:\n{results_text}',
        lane='cross_domain',
        max_tokens=1024,
    )

    log_event('coordinator_done', {'query': query, 'sub_count': len(sub_tasks)})
    return {
        'query': query,
        'sub_tasks': sub_tasks,
        'sub_results': results,
        'final_output': merged,
        'ts_start': ts_start,
        'ts_end': datetime.utcnow().isoformat(),
    }

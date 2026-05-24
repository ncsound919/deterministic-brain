from __future__ import annotations
import hashlib
import json
import os
import tempfile
import sqlite3
import logging
import time
import warnings
from contextlib import closing

logger = logging.getLogger(__name__)
from datetime import datetime
from typing import Any, Dict, List

from config import cfg

warnings.filterwarnings("ignore", category=UserWarning,
                        message=r"Api key is used with an insecure connection")
warnings.filterwarnings("ignore", category=UserWarning,
                        message=r"Failed to obtain server version")


def _wal_conn(db_path: str):
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _qdrant_client():
    url = os.getenv('QDRANT_URL')
    key = os.getenv('QDRANT_API_KEY')
    try:
        from qdrant_client import QdrantClient
        if url:
            return QdrantClient(url=url, api_key=key, timeout=5,
                                check_compatibility=False)
    except ImportError:
        pass
    return None


def _neo4j_driver():
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER', 'neo4j')
    pwd = os.getenv('NEO4J_PASSWORD', '')
    try:
        from neo4j import GraphDatabase
        if uri:
            return GraphDatabase.driver(uri, auth=(user, pwd))
    except ImportError:
        pass
    return None


def analyze_session_patterns(db_path: str = "traces.db") -> Dict:
    patterns = {
        "total_sessions": 0,
        "sessions_by_status": {},
        "sessions_by_lane": {},
        "avg_confidence": {},
        "failed_queries": [],
        "common_keywords": {},
    }

    try:
        with closing(_wal_conn(db_path)) as conn:
            cursor = conn.execute("SELECT data FROM events WHERE event = 'handle'")
            while True:
                batch = cursor.fetchmany(500)
                if not batch:
                    break
                for (row,) in batch:
                    try:
                        data = json.loads(row)
                    except Exception:
                        continue

                    status = data.get("status", "unknown")
                    task_data = data.get("task", {})
                    lane = task_data.get("task", "unknown") if isinstance(task_data, dict) else "unknown"
                    conf = data.get("confidence", 0.0)
                    query = data.get("query", "")

                    patterns["total_sessions"] += 1
                    patterns["sessions_by_status"][status] = patterns["sessions_by_status"].get(status, 0) + 1
                    patterns["sessions_by_lane"][lane] = patterns["sessions_by_lane"].get(lane, 0) + 1

                    if lane not in patterns["avg_confidence"]:
                        patterns["avg_confidence"][lane] = []
                    patterns["avg_confidence"][lane].append(conf)

                    if status in ("failed", "low_confidence", "blocked"):
                        patterns["failed_queries"].append({
                            "query": query[:100],
                            "status": status,
                            "confidence": conf,
                        })

                    for word in query.lower().split():
                        if len(word) > 3:
                            patterns["common_keywords"][word] = patterns["common_keywords"].get(word, 0) + 1

        for lane in patterns["avg_confidence"]:
            vals = patterns["avg_confidence"][lane]
            patterns["avg_confidence"][lane] = round(sum(vals) / len(vals), 4) if vals else 0

        patterns["common_keywords"] = dict(
            sorted(patterns["common_keywords"].items(), key=lambda x: -x[1])[:20]
        )

    except Exception as e:
        logger.exception("[autodream] analyze_session_patterns failed")
        patterns["error"] = str(e)

    return patterns


def deduplicate_qdrant(collection_name: str, dry_run: bool = False) -> Dict:
    client = _qdrant_client()
    if client is None:
        return {"status": "skipped", "reason": "qdrant_not_configured"}

    removed = 0
    seen_hashes: Dict[str, Any] = {}
    offset = None

    try:
        while True:
            points_result = client.scroll(
                collection_name=collection_name,
                limit=200,
                offset=offset,
            )
            points = points_result[0] if points_result else []
            if not points:
                break
            next_offset = points_result[1] if len(points_result) > 1 else None

            for p in points:
                payload = p.payload or {}
                text = payload.get("text", payload.get("content", ""))
                h = hashlib.sha256(text.encode()).hexdigest()[:16]

                if h in seen_hashes:
                    if not dry_run:
                        client.delete(
                            collection_name=collection_name,
                            points_selector=[p.id],
                        )
                    removed += 1
                else:
                    seen_hashes[h] = p.id

            if not next_offset:
                break
            offset = next_offset

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    return {"status": "ok", "removed": removed, "kept": len(seen_hashes)}


def optimize_neo4j(dry_run: bool = False) -> Dict:
    driver = _neo4j_driver()
    if driver is None:
        return {"status": "skipped", "reason": "neo4j_not_configured"}

    merged = 0
    pruned_nodes = 0

    try:
        with driver.session() as session:
            result = session.run(
                "MATCH (n) WITH n.id AS nid, collect(n) AS nodes "
                "WHERE size(nodes) > 1 RETURN nid, nodes"
            )
            for record in result:
                nodes = record["nodes"]
                if len(nodes) > 1 and not dry_run:
                    keep = nodes[0]
                    tx = session.begin_transaction()
                    try:
                        for n in nodes[1:]:
                            tx.run(
                                "MATCH (a), (b) WHERE id(a) = $keep_id AND id(b) = $del_id "
                                "SET a.count = coalesce(a.count, 1) + 1 "
                                "WITH a, b MATCH (b)-[r]-() DELETE r, b",
                                keep_id=keep.id, del_id=n.id,
                            )
                            merged += 1
                        tx.commit()
                    except Exception:
                        tx.rollback()
                        raise

            result = session.run(
                "MATCH (n) WHERE NOT (n)--() DELETE n RETURN count(n) AS cnt"
            )
            pruned_nodes = result.single()["cnt"] or 0

    except Exception as e:
        return {"status": "error", "reason": str(e)}
    finally:
        driver.close()

    return {"status": "ok", "merged": merged, "pruned_nodes": pruned_nodes}


def vacuum_traces(db_path: str = "traces.db", retention_days: int = 30, dry_run: bool = False) -> Dict:
    size_before = os.path.getsize(db_path) if os.path.exists(db_path) else 0
    cutoff = time.time() - (retention_days * 86400)

    removed = 0

    if not dry_run:
        try:
            with closing(_wal_conn(db_path)) as conn:
                cur = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
                removed = cur.rowcount
                conn.commit()
        except Exception as e:
            return {"status": "error", "reason": f"delete_failed: {e}"}

        try:
            with closing(_wal_conn(db_path)) as conn:
                conn.execute("VACUUM")
                conn.commit()
        except Exception as e:
            logger.warning("[autodream] VACUUM failed (non-fatal): %s", e)

    size_after = os.path.getsize(db_path)

    return {
        "status": "ok",
        "removed_events": removed,
        "size_before_mb": round(size_before / 1024 / 1024, 2),
        "size_after_mb": round(size_after / 1024 / 1024, 2),
    }


def analyze_and_correct(config_file: str = ".autodream_corrections.jsonl") -> List[Dict]:
    # Read existing corrections to avoid duplicates
    existing_patterns = set()
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entry = json.loads(line)
                            existing_patterns.add(json.dumps(entry.get("pattern_keywords", []), sort_keys=True))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass

    corrections = []
    new_corrections = []

    try:
        with closing(_wal_conn("traces.db")) as conn:
            rows = conn.execute(
                "SELECT data FROM events WHERE event = 'handle' "
                "AND (data LIKE '%\"status\": \"failed\"%' OR data LIKE '%\"status\": \"low_confidence\"%')"
            ).fetchall()

            for r in rows:
                try:
                    data = json.loads(r[0])
                except Exception:
                    continue

                query = data.get("query", "")
                reasoning = data.get("reasoning", {})
                chosen = reasoning.get("chosen_skill", "")

                if not chosen:
                    continue

                keywords = list(set(w.lower() for w in query.split() if len(w) > 3))[:5]
                correction = {
                    "ts": datetime.utcnow().isoformat(),
                    "pattern_keywords": keywords,
                    "failed_skill": chosen,
                    "confidence": reasoning.get("confidence", 0.0),
                    "suggested_action": "review_skill_selection",
                }
                corrections.append(correction)

        # Filter out duplicates
        for c in corrections:
            pattern_key = json.dumps(c.get("pattern_keywords", []), sort_keys=True)
            if pattern_key not in existing_patterns:
                existing_patterns.add(pattern_key)
                new_corrections.append(c)

        if new_corrections:
            with open(config_file, "a") as f:
                for c in new_corrections:
                    f.write(json.dumps(c) + "\n")

    except Exception as e:
        logger.exception("[autodream] analyze_and_correct failed")
        new_corrections = [{"error": str(e)}]

    return new_corrections


def _run_swarm_cycle(dry_run: bool = False) -> Dict:
    try:
        from orchestration.swarm_worker import get_swarm_worker
        worker = get_swarm_worker()
        if dry_run:
            queue = worker.get_queue()
            pending = [t for t in queue if t.get("status") == "pending"]
            return {"status": "dry_run", "pending_count": len(pending)}
        result = worker.tick()
        return result
    except ImportError:
        return {"status": "skipped", "reason": "swarm_worker_not_loaded"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def _run_repo_inventory_cycle(dry_run: bool = False) -> Dict:
    try:
        from features.repo_inventory import get_repo_inventory
        inventory = get_repo_inventory()
        if dry_run:
            return {"status": "dry_run", "total": inventory.get_stats()["total"]}
        result = inventory.refresh()
        if result.get("status") == "ok":
            inventory.auto_queue(max_per_run=3)
        return result
    except ImportError:
        return {"status": "skipped", "reason": "repo_inventory_not_loaded"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def consolidate_knowledge_bank(dry_run: bool = False) -> Dict:
    result = {"status": "skipped", "reason": "knowledge_bank_not_loaded"}

    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        if not bank.loaded:
            return result

        dupes = bank.find_near_duplicates(threshold=0.92)
        merged = 0
        if not dry_run:
            for group in dupes:
                bank.merge_fragments(group)
                merged += len(group) - 1
        else:
            merged = sum(len(g) - 1 for g in dupes)

        if not dry_run:
            bank.age_decay(stale_days=30, decay_factor=0.95)
            pruned = bank.prune_stale(min_confidence=0.1)
        else:
            pruned = 0

        refs_generated = 0
        clusters = bank.cluster_by_tags(min_size=5)
        if not dry_run:
            for tag, frags in clusters.items():
                bank.generate_ref_doc(tag, frags)
                refs_generated += 1

        result = {
            "status": "ok",
            "duplicate_groups_found": len(dupes),
            "fragments_merged": merged,
            "fragments_pruned": pruned,
            "refs_generated": refs_generated,
            "tag_clusters": {k: len(v) for k, v in clusters.items()},
        }

    except Exception as e:
        result = {"status": "error", "reason": str(e)}

    return result


def run_autodream(dry_run: bool = False) -> Dict:
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "session_patterns": analyze_session_patterns(),
        "qdrant_dedup": {},
        "neo4j_optimize": {},
        "traces_vacuum": {},
        "knowledge_bank_consolidation": {},
        "corrections": [],
    }

    for collection in ["code_kb", "policy_kb", "agent_kb", "tools_kb", "general_kb"]:
        results["qdrant_dedup"][collection] = deduplicate_qdrant(collection, dry_run)

    from brain.correction_detector import run_correction_detection

    session_trace = []
    with closing(_wal_conn("traces.db")) as conn:
        rows = conn.execute(
            "SELECT data FROM events WHERE event = 'handle'"
        ).fetchall()
        for r in rows:
            try:
                data = json.loads(r[0])
                session_trace.append({
                    "skill": data.get("task", {}).get("task", "unknown") if isinstance(data.get("task"), dict) else str(data.get("task", "unknown")),
                    "status": data.get("status", "unknown"),
                    "timestamp": datetime.utcnow(),
                    "error": data.get("error"),
                })
            except Exception:
                continue

    corrections_written = run_correction_detection(session_trace)

    results["neo4j_optimize"] = optimize_neo4j(dry_run)
    results["traces_vacuum"] = vacuum_traces(retention_days=cfg.trace_retention_days, dry_run=dry_run)
    results["corrections_written"] = corrections_written
    results["corrections"] = analyze_and_correct()
    
    results["knowledge_bank_consolidation"] = consolidate_knowledge_bank(dry_run=dry_run)

    results["swarm_work"] = _run_swarm_cycle(dry_run=dry_run)
    results["repo_inventory"] = _run_repo_inventory_cycle(dry_run=dry_run)

    output_path = ".autodream_last_run.json"
    fd, tmp_path = tempfile.mkstemp(dir=".", suffix=".autodream.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(results, f, indent=2)
        os.replace(tmp_path, output_path)
    except Exception:
        os.unlink(tmp_path)
        raise

    # Emit event for cross-system listeners (skill evolver, runtime healer)
    try:
        from orchestration.event_bus import event_bus
        if corrections_written > 0:
            event_bus.emit("correction_found", {"count": corrections_written})
        event_bus.emit("autodream_run", dry_run=dry_run,
                       corrections_count=len(results["corrections"]),
                       corrections_written=corrections_written)
        for corr in results["corrections"]:
            event_bus.emit("skill_failure",
                skill_id=corr.get("failed_skill", "unknown"),
                confidence=corr.get("confidence", 0.0),
                suggested_action=corr.get("suggested_action", ""))
    except ImportError:
        pass

    return results

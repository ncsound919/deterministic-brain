from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import cfg


def _qdrant_client():
    url = os.getenv('QDRANT_URL')
    key = os.getenv('QDRANT_API_KEY')
    try:
        from qdrant_client import QdrantClient
        if url:
            return QdrantClient(url=url, api_key=key)
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
    conn = sqlite3.connect(db_path)
    patterns = {
        "total_sessions": 0,
        "sessions_by_status": {},
        "sessions_by_lane": {},
        "avg_confidence": {},
        "failed_queries": [],
        "common_keywords": {},
    }

    try:
        rows = conn.execute(
            "SELECT data FROM events WHERE event = 'handle'"
        ).fetchall()

        for r in rows:
            try:
                data = json.loads(r[0])
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
        patterns["error"] = str(e)
    finally:
        conn.close()

    return patterns


def deduplicate_qdrant(collection_name: str, dry_run: bool = False) -> Dict:
    client = _qdrant_client()
    if client is None:
        return {"status": "skipped", "reason": "qdrant_not_configured"}

    removed = 0
    seen_hashes: Dict[str, Any] = {}

    try:
        points_result = client.scroll(collection_name=collection_name, limit=1000)
        points = points_result[0] if points_result else []

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
                    for n in nodes[1:]:
                        session.run(
                            "MATCH (a), (b) WHERE id(a) = $keep_id AND id(b) = $del_id "
                            "SET a.count = coalesce(a.count, 1) + 1 "
                            "WITH a, b MATCH (b)-[r]-() DELETE r, b",
                            keep_id=keep.id, del_id=n.id,
                        )
                        merged += 1

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

    conn = sqlite3.connect(db_path)
    removed = 0

    try:
        if not dry_run:
            cur = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            removed = cur.rowcount
            conn.commit()
            conn.execute("VACUUM")
            conn.commit()

        size_after = os.path.getsize(db_path)
        conn.close()

    except Exception as e:
        conn.close()
        return {"status": "error", "reason": str(e)}

    return {
        "status": "ok",
        "removed_events": removed,
        "size_before_mb": round(size_before / 1024 / 1024, 2),
        "size_after_mb": round(size_after / 1024 / 1024, 2),
    }


def analyze_and_correct(config_file: str = ".autodream_corrections.jsonl") -> List[Dict]:
    conn = sqlite3.connect("traces.db")
    corrections = []

    try:
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

        if corrections:
            with open(config_file, "a") as f:
                for c in corrections:
                    f.write(json.dumps(c) + "\n")

    except Exception as e:
        corrections = [{"error": str(e)}]
    finally:
        conn.close()

    return corrections


def run_autodream(dry_run: bool = False) -> Dict:
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "session_patterns": analyze_session_patterns(),
        "qdrant_dedup": {},
        "neo4j_optimize": {},
        "traces_vacuum": {},
        "corrections": [],
    }

    for collection in ["code_kb", "policy_kb", "agent_kb", "tools_kb", "general_kb"]:
        results["qdrant_dedup"][collection] = deduplicate_qdrant(collection, dry_run)

    results["neo4j_optimize"] = optimize_neo4j(dry_run)
    results["traces_vacuum"] = vacuum_traces(retention_days=cfg.trace_retention_days, dry_run=dry_run)
    results["corrections"] = analyze_and_correct()

    output_path = ".autodream_last_run.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    return results

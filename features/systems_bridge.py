"""External Systems Bridge — Connects the Brain to Superalgos, Content Engine, etc.
"""
import os
import sys
import json
import logging
import subprocess
import uuid
import threading
import time
import uuid
import threading
import time
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ExternalSystemsBridge:
    def check_superalgos(self) -> Dict:
        """Monitor the status of the Superalgos-master directory."""
        path = "Superalgos-master"
        if not os.path.exists(path):
            return {"status": "error", "message": "Superalgos directory not found"}

        logs_path = os.path.join(path, "Reports")
        active_bots = 0
        if os.path.exists(logs_path):
            active_bots = len([d for d in os.listdir(logs_path) if os.path.isdir(os.path.join(logs_path, d))])

        return {
            "status": "online" if active_bots > 0 else "standby",
            "active_bots": active_bots,
            "path": path,
            "version": "1.0.0-master"
        }

    def run_content_pipeline(self, topic: str, format: str = "podcast") -> Dict:
        """Trigger the Content-Creation-Engine pipeline (Hood Alchemy).
        Runs the actual pipeline.py subprocess in the background.
        """
        engine_path = "Content-Creation-Engine--main"
        pipeline_script = os.path.join(engine_path, "pipeline.py")
        if not os.path.exists(pipeline_script):
            return {"status": "error", "message": f"Pipeline script not found at {pipeline_script}"}

        episode_id = f"ep_{int(time.time())}"
        run_id = str(uuid.uuid4())

        def _run_pipeline():
            try:
                subprocess.run(
                    [sys.executable, pipeline_script,
                     "--episode", episode_id,
                     "--run-id", run_id,
                     "--topic", topic,
                     "--dry-run"],
                    cwd=engine_path,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                )
            except Exception as e:
                logger.error(f"Pipeline subprocess failed: {e}")

        thread = threading.Thread(target=_run_pipeline, daemon=True)
        thread.start()

        return {
            "status": "triggered",
            "topic": topic,
            "format": format,
            "episode_id": episode_id,
            "run_id": run_id,
            "message": f"Pipeline started for {topic} in {format} format."
        }

    def get_benchmark_summary(self) -> Dict:
        """Read the last report from benchmark_harness."""
        report_path = ".benchmarks/report.json"
        if os.path.exists(report_path):
            try:
                with open(report_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"status": "no_report", "message": "Run benchmark_harness.py to generate metrics."}

    def get_content_pipeline_status(self, episode_id: str) -> Dict:
        """Check pipeline status for an episode via SupabaseWriter state."""
        episode_dir = os.path.join("Content-Creation-Engine--main", "episodes", episode_id)
        log_path = os.path.join(episode_dir, "pipeline_run.log")
        if not os.path.exists(log_path):
            return {"status": "unknown", "episode_id": episode_id}
        with open(log_path, "r") as f:
            lines = f.readlines()
        return {
            "status": "complete" if any("Pipeline complete" in l for l in lines) else "running",
            "episode_id": episode_id,
            "last_line": lines[-1].strip() if lines else "",
        }

_BRIDGE = ExternalSystemsBridge()

def get_systems_bridge():
    return _BRIDGE

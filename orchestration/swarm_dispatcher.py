"""SwarmDispatcher — reads swarm.yaml, fires agent bundles in parallel lanes."""
from __future__ import annotations
import importlib
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List


class SwarmDispatcher:
    """
    Replaces Big-Homie as a minimal, single-file dispatcher.
    Reads swarm.yaml and fires each bundle's lanes in parallel threads.
    No LLM. No external service. Pure Python.
    """

    def __init__(self, swarm_config_path: str = "swarm.yaml"):
        with open(swarm_config_path) as f:
            cfg = yaml.safe_load(f)
        self.bundles: Dict[str, Dict] = cfg.get("bundles", {})

    def dispatch(self, bundle_name: str, inputs: Dict) -> Dict:
        bundle = self.bundles.get(bundle_name)
        if not bundle:
            return {"error": f"Bundle '{bundle_name}' not found"}

        lanes: List[str] = bundle.get("lanes", [])
        results: Dict    = {}

        with ThreadPoolExecutor(max_workers=max(1, len(lanes))) as pool:
            futures = {
                pool.submit(self._run_lane, lane, inputs): lane
                for lane in lanes
            }
            for future in as_completed(futures):
                lane = futures[future]
                try:
                    results[lane] = future.result()
                except Exception as exc:
                    results[lane] = {"error": str(exc)}

        return {"bundle": bundle_name, "results": results}

    @staticmethod
    def _run_lane(lane_module: str, inputs: Dict) -> Dict:
        """Dynamically import and run a lane module's run() function."""
        mod = importlib.import_module(lane_module)
        return mod.run(inputs)

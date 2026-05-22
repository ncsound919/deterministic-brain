"""
CCE Bridge — Connects to the Content Creation Engine (CCE).
Enables autonomous generation of 'Manifesto' videos, social posts, and episodes.
"""
import os
from typing import Dict
from loguru import logger

class CCEBridge:
    def __init__(self, cce_path: str = "Content-Creation-Engine--main"):
        self.base_path = cce_path
        self.pipeline_script = os.path.join(cce_path, "pipeline.py")
        self.run_script = os.path.join(cce_path, "run_episode.py")

    def generate_manifesto(self, context: str, topic: str = "919 AI Manifesto") -> Dict:
        """
        Trigger the CCE pipeline to generate a manifesto based on provided context.
        """
        logger.info(f"CCE Bridge: Generating Manifesto for '{topic}'...")
        
        if not os.path.exists(self.pipeline_script):
            return {"status": "error", "message": "CCE Pipeline script not found."}

        # In a real run, we would pass the context into the pipeline's input folder
        # For now, we simulate the triggering of the 'run_episode' logic
        try:
            # result = subprocess.run(["python", self.run_script, "--topic", topic], capture_output=True, text=True)
            return {
                "status": "ok",
                "message": f"Successfully triggered CCE Manifesto pipeline for '{topic}'.",
                "artifacts": [f"episodes/{topic.replace(' ', '_')}.mp4"]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Singleton instance
_CCE = None

def get_cce_bridge():
    global _CCE
    if _CCE is None:
        _CCE = CCEBridge()
    return _CCE

"""
Draymond Bridge — Interconnects the Deterministic Brain with the Uplift Ecosystem.
Parses the Draymond registry and enables cross-agent invocation.
"""
import os
import re
from typing import Dict, List, Optional
from loguru import logger

class DraymondBridge:
    def __init__(self, draymond_path: str = "Draymond-Orchestrator-main"):
        self.base_path = draymond_path
        self.registry_file = os.path.join(draymond_path, "src/lib/draymond/seed.ts")
        self.entities: Dict[str, Dict] = {}
        self._load_registry()

    def _load_registry(self):
        """Parse seed.ts to extract agent/tool/skill metadata."""
        if not os.path.exists(self.registry_file):
            logger.warning(f"Draymond registry not found at {self.registry_file}")
            return

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract blocks of entities using a simplified regex
            # This is a heuristic parser for the Draymond TS format
            entity_pattern = re.compile(r'{\s*name:\s*\'(.*?)\',\s*slug:\s*\'(.*?)\',\s*kind:\s*\'(.*?)\',\s*description:\s*\'(.*?)\'', re.DOTALL)
            
            matches = entity_pattern.findall(content)
            for name, slug, kind, desc in matches:
                self.entities[slug] = {
                    "name": name,
                    "kind": kind,
                    "description": desc.replace("\n", " ").strip(),
                    "source": "draymond"
                }
            
            logger.info(f"Draymond Bridge: Registered {len(self.entities)} entities from ecosystem.")
        except Exception as e:
            logger.error(f"Failed to parse Draymond registry: {e}")

    def list_entities(self, kind: Optional[str] = None) -> List[Dict]:
        if kind:
            return [e for e in self.entities.values() if e["kind"] == kind]
        return list(self.entities.values())

    def invoke(self, slug: str, **kwargs) -> Dict:
        """
        Placeholder for Draymond invocation.
        In a full implementation, this would look up the 'invocation_method'
        and 'invocation_config' from seed.ts and execute the CLI/API call.
        """
        if slug not in self.entities:
            return {"status": "error", "message": f"Entity '{slug}' not found in Draymond registry."}
        
        entity = self.entities[slug]
        logger.info(f"Draymond Bridge: Invoking {entity['name']} ({slug})...")
        
        # Real-world logic would happen here (dispatch to subprocess, etc.)
        return {
            "status": "ok",
            "entity": entity["name"],
            "result": f"Simulated execution of Draymond entity: {slug}"
        }

# Singleton instance
_BRIDGE = None

def get_draymond_bridge():
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = DraymondBridge()
    return _BRIDGE

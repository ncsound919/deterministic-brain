
import asyncio
import os
import sys
from typing import Dict, Any, List
from tools.mcp_client import MCPClient

VIBESERVE_DIR = r"C:\Users\User\Downloads\Skilltech\VibeServe-MCP"
VIBESERVE_SERVER = os.path.join(VIBESERVE_DIR, "vibeserve.py")

class VibeServeBridge:
    def __init__(self):
        # Run using the same python interpreter
        self.client = MCPClient(server_command=[sys.executable, VIBESERVE_SERVER])
        self._connected = False

    async def _ensure_connected(self):
        if not self._connected:
            self._connected = await self.client.connect()

    async def generate_ui(self, page_type: str, requirements: List[str], target_audience: str = "general users") -> Dict[str, Any]:
        """Generate a production-ready UI specification with multi-agent critique."""
        await self._ensure_connected()
        return await self.client.call_tool("generate_ui_spec", {
            "ctx": {},
            "page_type": page_type,
            "requirements": requirements,
            "target_audience": target_audience
        })

    async def validate_ui(self, specification: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a UI spec against design systems and WCAG AAA standards."""
        await self._ensure_connected()
        return await self.client.call_tool("validate_ui_spec", {"ctx": {}, "specification": specification})

    async def get_design_systems(self) -> Dict[str, Any]:
        """List available design systems and brand tokens."""
        await self._ensure_connected()
        return await self.client.call_tool("list_design_systems", {"ctx": {}})

# Singleton
_bridge = VibeServeBridge()

def vibe_generate(page_type: str, requirements: List[str], audience: str = "general users") -> Dict[str, Any]:
    return asyncio.run(_bridge.generate_ui(page_type, requirements, audience))

def vibe_validate(spec: Dict[str, Any]) -> Dict[str, Any]:
    return asyncio.run(_bridge.validate_ui(spec))

def vibe_list_systems() -> Dict[str, Any]:
    return asyncio.run(_bridge.get_design_systems())

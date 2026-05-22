
import asyncio
from typing import Dict, Any, Optional
from tools.mcp_client import MCPClient

BIZ_LOGIC_PATH = r"C:\Users\User\Downloads\Skilltech\Business-Logic-MCP-main\Business logic mcp"

class BusinessLogicBridge:
    def __init__(self):
        # We run it using node
        self.client = MCPClient(server_command=["node", BIZ_LOGIC_PATH])
        self._connected = False

    async def _ensure_connected(self):
        if not self._connected:
            self._connected = await self.client.connect()

    async def get_entity_rules(self, entity: str) -> Dict[str, Any]:
        """Consult business logic for entity rules and constraints."""
        await self._ensure_connected()
        return await self.client.call_tool("get_entity_rules", {"entity": entity})

    async def get_footguns(self, entity: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve known development pitfalls for a domain."""
        await self._ensure_connected()
        return await self.client.call_tool("get_footguns", {"entity": entity} if entity else {})

    async def get_cross_system_effects(self, operation: str) -> Dict[str, Any]:
        """Check downstream effects of a specific operation (e.g. user.email_changed)."""
        await self._ensure_connected()
        return await self.client.call_tool("get_cross_system_effects", {"operation": operation})

# Singleton instance to persist the process
_bridge = BusinessLogicBridge()

def biz_get_rules(entity: str) -> Dict[str, Any]:
    return asyncio.run(_bridge.get_entity_rules(entity))

def biz_get_footguns(entity: Optional[str] = None) -> Dict[str, Any]:
    return asyncio.run(_bridge.get_footguns(entity))

def biz_get_effects(operation: str) -> Dict[str, Any]:
    return asyncio.run(_bridge.get_cross_system_effects(operation))

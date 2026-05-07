"""MCP Client tool — interface with MCP servers for extended capabilities."""
from __future__ import annotations
import os
import json
import logging
from typing import Any, Dict, Optional, List
import asyncio

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP servers via stdio or HTTP."""

    def __init__(self, server_command: Optional[List[str]] = None, server_url: Optional[str] = None):
        self.server_command = server_command
        self.server_url = server_url
        self._process = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection to MCP server."""
        if self.server_url:
            self._connected = True
            logger.info(f"Connected to MCP server via URL: {self.server_url}")
            return True
        
        if self.server_command:
            try:
                self._process = await asyncio.create_subprocess_exec(
                    *self.server_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                self._connected = True
                logger.info(f"Started MCP server process: {self.server_command}")
                return True
            except Exception as e:
                logger.error(f"Failed to start MCP server: {e}")
                return False
        return False

    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
        self._connected = False
        logger.info("Disconnected from MCP server")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self._connected:
            return {"error": "Not connected to MCP server"}
        
        if self._process:
            request = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            })
            self._process.stdin.write((request + "\n").encode())
            await self._process.stdin.drain()
            
            response_line = await self._process.stdout.readline()
            if response_line:
                return json.loads(response_line.decode())
        
        return {"error": "No response from MCP server"}

    async def list_tools(self) -> List[Dict[str, str]]:
        """List available tools on the MCP server."""
        if not self._connected:
            return []
        
        if self._process:
            request = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            })
            self._process.stdin.write((request + "\n").encode())
            await self._process.stdin.drain()
            
            response_line = await self._process.stdout.readline()
            if response_line:
                data = json.loads(response_line.decode())
                return data.get("result", {}).get("tools", [])
        
        return []


def mcp_connect(server_command: Optional[List[str]] = None, server_url: Optional[str] = None) -> Dict[str, Any]:
    """Connect to an MCP server.
    
    Args:
        server_command: Command and args to start MCP server (e.g., ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/path"])
        server_url: HTTP URL for MCP server (e.g., "http://localhost:8080/mcp")
    
    Returns:
        Dict with connection status and client info
    """
    client = MCPClient(server_command=server_command, server_url=server_url)
    loop = asyncio.new_event_loop()
    try:
        success = loop.run_until_complete(client.connect())
        return {
            "connected": success,
            "client_type": "stdio" if server_command else "http",
            "endpoint": server_url or " ".join(server_command) if server_command else None
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
    finally:
        loop.close()


def mcp_call(tool_name: str, arguments: Dict[str, Any], server_url: Optional[str] = None) -> Dict[str, Any]:
    """Call a tool on a connected MCP server.
    
    Args:
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        server_url: URL of the MCP server (for HTTP mode)
    
    Returns:
        Tool response dict
    """
    import requests
    
    if server_url:
        try:
            resp = requests.post(
                server_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments}
                },
                timeout=30
            )
            return resp.json().get("result", {})
        except Exception as e:
            return {"error": str(e)}
    
    return {"error": "No server URL provided"}


def mcp_list_tools(server_url: Optional[str] = None) -> List[Dict[str, str]]:
    """List available tools on MCP server.
    
    Args:
        server_url: URL of the MCP server
    
    Returns:
        List of tool definitions
    """
    import requests
    
    if server_url:
        try:
            resp = requests.post(
                server_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list"
                },
                timeout=10
            )
            return resp.json().get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []
    
    return []


def mcp_server_available(port: int = 8080) -> bool:
    """Check if an MCP server is running on the given port.
    
    Args:
        port: Port to check
    
    Returns:
        True if server is reachable
    """
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except Exception:
        return False
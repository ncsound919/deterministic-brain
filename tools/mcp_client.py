"""MCP Client tool — interface with MCP servers for extended capabilities."""
from __future__ import annotations
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
        self._request_id = 1
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._read_task = None
        self._stderr_task = None

    async def _read_loop(self):
        """Background loop to read from stdout and dispatch to pending requests."""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if not decoded:
                    continue
                try:
                    data = json.loads(decoded)
                    if isinstance(data, dict) and "jsonrpc" in data:
                        req_id = data.get("id")
                        if req_id in self._pending_requests:
                            self._pending_requests[req_id].set_result(data)
                            del self._pending_requests[req_id]
                        else:
                            logger.debug(f"Received JSON-RPC message with no pending request: {data}")
                except json.JSONDecodeError:
                    logger.debug(f"Skipping non-JSON output: {decoded}")
        except Exception as e:
            logger.error(f"Read loop error: {e}")
        finally:
            # Wake up all pending requests with an error
            for fut in self._pending_requests.values():
                if not fut.done():
                    fut.set_exception(RuntimeError("MCP server disconnected"))
            self._pending_requests.clear()

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
                
                # Start read loops before handshake
                self._read_task = asyncio.create_task(self._read_loop())
                self._stderr_task = asyncio.create_task(self._log_stderr())

                # Handshake: initialize
                init_fut = asyncio.Future()
                self._pending_requests[0] = init_fut
                
                init_request = json.dumps({
                    "jsonrpc": "2.0",
                    "id": 0,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "DeterministicBrain", "version": "1.0.0"}
                    }
                })
                self._process.stdin.write((init_request + "\n").encode())
                await self._process.stdin.drain()
                
                # Wait for init response with timeout
                try:
                    await asyncio.wait_for(init_fut, timeout=10.0)
                except asyncio.TimeoutError:
                    logger.error("MCP initialization timed out")
                    await self.disconnect()
                    return False
                
                # Handshake: initialized notification
                initialized_notif = json.dumps({
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized"
                })
                self._process.stdin.write((initialized_notif + "\n").encode())
                await self._process.stdin.drain()

                self._connected = True
                logger.info(f"Started and initialized MCP server process: {self.server_command}")
                return True
            except Exception as e:
                logger.error(f"Failed to start MCP server: {e}")
                return False
        return False

    async def _log_stderr(self):
        """Read and log stderr output from the server process."""
        try:
            while self._process and self._process.stderr:
                line = await self._process.stderr.readline()
                if not line:
                    break
                logger.error(f"MCP Server Error: {line.decode().strip()}")
        except Exception as e:
            logger.debug(f"Error reading stderr: {e}")

    async def disconnect(self) -> None:
        """Close connection to MCP server."""
        self._connected = False
        if self._read_task:
            self._read_task.cancel()
        if self._stderr_task:
            self._stderr_task.cancel()
        
        if self._process:
            try:
                # Close pipes
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                await self._process.wait()
            except Exception as e:
                logger.debug(f"Error during process termination: {e}")
            finally:
                self._process = None
        
        logger.info("Disconnected from MCP server")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Call a tool on the MCP server."""
        if not self._connected:
            if not await self.connect():
                return {"error": "Failed to connect to MCP server"}
        
        if self._process:
            req_id = self._request_id
            self._request_id += 1
            
            fut = asyncio.Future()
            self._pending_requests[req_id] = fut
            
            try:
                request = json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                })
                self._process.stdin.write((request + "\n").encode())
                await self._process.stdin.drain()
                
                response = await asyncio.wait_for(fut, timeout=timeout)
                if "error" in response:
                    return {"error": response["error"]}
                return response.get("result", {})
            except asyncio.TimeoutError:
                if req_id in self._pending_requests:
                    del self._pending_requests[req_id]
                return {"error": f"Tool call '{tool_name}' timed out after {timeout}s"}
            except Exception as e:
                if req_id in self._pending_requests:
                    del self._pending_requests[req_id]
                logger.error(f"Tool call failed: {e}")
                return {"error": str(e)}
        
        return {"error": "Not connected"}

    async def list_tools(self, timeout: float = 10.0) -> List[Dict[str, str]]:
        """List available tools on the MCP server."""
        if not self._connected:
            if not await self.connect():
                return []
        
        if self._process:
            req_id = self._request_id
            self._request_id += 1
            
            fut = asyncio.Future()
            self._pending_requests[req_id] = fut
            
            try:
                request = json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": "tools/list"
                })
                self._process.stdin.write((request + "\n").encode())
                await self._process.stdin.drain()
                
                response = await asyncio.wait_for(fut, timeout=timeout)
                return response.get("result", {}).get("tools", [])
            except Exception as e:
                if req_id in self._pending_requests:
                    del self._pending_requests[req_id]
                logger.error(f"Failed to list tools: {e}")
                return []
        
        return []


def mcp_connect(server_command: Optional[List[str]] = None, server_url: Optional[str] = None) -> Dict[str, Any]:
    """Connect to an MCP server."""
    client = MCPClient(server_command=server_command, server_url=server_url)
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        success = loop.run_until_complete(client.connect())
        return {
            "connected": success,
            "client_type": "stdio" if server_command else "http",
            "endpoint": server_url or " ".join(server_command) if server_command else None
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


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
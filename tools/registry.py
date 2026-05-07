"""MCP Tool Registry — maps tool names to Python callables."""
from __future__ import annotations
from typing import Any, Callable, Dict
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._register_defaults()

    def _register_defaults(self):
        from tools.file_io import file_write, file_read
        from tools.linter import run_linter
        import subprocess
        
        self.register("file_write",  file_write)
        self.register("file_read",   file_read)
        self.register("run_linter",   run_linter)
        self.register("run_command", lambda cmd: subprocess.run(
            cmd.split(), capture_output=True, text=True, check=True))
        
        self._register_optional_tools()

    def _register_optional_tools(self):
        # Email sender
        try:
            from tools.email_sender import send_email
            self.register("send_email", send_email)
            logger.info("Registered tool: send_email")
        except ImportError as e:
            logger.debug(f"send_email not available: {e}")

        try:
            from tools.web_fetcher import web_fetch
            self.register("web_fetch", web_fetch)
            logger.info("Registered tool: web_fetch")
        except ImportError as e:
            logger.debug(f"web_fetch not available: {e}")
        
        try:
            from tools.browser.controller import BrowserController
            browser = BrowserController()
            self.register("browser_navigate", browser.navigate)
            self.register("browser_click", browser.click)
            self.register("browser_screenshot", browser.screenshot)
            self.register("browser_fill", browser.fill_form)
            logger.info("Registered tools: browser_*")
        except ImportError as e:
            logger.debug(f"browser tools not available: {e}")
        
        try:
            import requests
            def http_request(method: str, url: str, headers: Dict = None, 
                           json: Dict = None, data: Any = None) -> Dict:
                resp = requests.request(method, url, headers=headers, json=json, data=data)
                return {"status": resp.status_code, "body": resp.text, "json": resp.json() if resp.headers.get("content-type","").startswith("application/json") else None}
            self.register("http_request", http_request)
            logger.info("Registered tool: http_request")
        except ImportError:
            logger.debug("requests not available for http_request")

        try:
            from tools.code_executor import execute_code
            self.register("execute_code", execute_code)
            logger.info("Registered tool: execute_code")
        except ImportError as e:
            logger.debug(f"execute_code not available: {e}")

    def register(self, name: str, fn: Callable) -> None:
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, **kwargs) -> Any:
        if not self.has(name):
            raise ValueError(f"Tool '{name}' not registered")
        return self._tools[name](**kwargs)
    
    def list_tools(self) -> Dict[str, str]:
        """List all available tools and their function names."""
        return {name: fn.__name__ for name, fn in self._tools.items()}

    def get_tool(self, name: str) -> Dict[str, Any]:
        """Get tool spec by name."""
        if name not in self._tools:
            return None
        fn = self._tools[name]
        import inspect
        sig = inspect.signature(fn)
        return {"name": name, "schema": {k: str(v) for k, v in sig.parameters.items()}, "fn": fn}

    def __iter__(self):
        """Iterate over tool specs."""
        for name, fn in self._tools.items():
            import inspect
            sig = inspect.signature(fn)
            yield {"name": name, "description": f"Tool: {fn.__name__}", "schema": {k: str(v) for k, v in sig.parameters.items()}}


def get_tool(name: str) -> Dict[str, Any]:
    """Get tool spec by name from global registry."""
    return tool_registry.get_tool(name)


tool_registry = ToolRegistry()

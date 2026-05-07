"""MCP Tool Registry — maps tool names to Python callables."""
from __future__ import annotations
from typing import Any, Callable, Dict


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
        self.register("run_linter",  run_linter)
        self.register("run_command", lambda cmd: subprocess.run(
            cmd.split(), capture_output=True, text=True, check=True))

    def register(self, name: str, fn: Callable) -> None:
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(self, name: str, **kwargs) -> Any:
        if not self.has(name):
            raise ValueError(f"Tool '{name}' not registered")
        return self._tools[name](**kwargs)

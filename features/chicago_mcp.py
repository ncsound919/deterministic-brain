from __future__ import annotations
"""
CHICAGO_MCP — Computer Use / screen control via MCP.

Exposes screen capture, mouse control, and keyboard injection through
the Model Context Protocol server interface. Integrates with the
brain's tool_calling lane and requires explicit permission approval.

Underlying engine: Playwright (browser) or pyautogui (desktop).
"""
import os
from typing import Any

try:
    import pyautogui
    _GUI_OK = True
except ImportError:
    _GUI_OK = False

_REQUIRE_APPROVAL = os.getenv('CHICAGO_REQUIRE_APPROVAL', 'true').lower() != 'false'


class ComputerUseSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.action_log: list[dict] = []

    def screenshot(self) -> dict:
        if not _GUI_OK:
            return {'error': 'pyautogui not installed. pip install pyautogui'}
        img = pyautogui.screenshot()
        return {'width': img.width, 'height': img.height, 'session': self.session_id}

    def click(self, x: int, y: int) -> dict:
        if _REQUIRE_APPROVAL:
            return {'blocked': True, 'reason': 'CHICAGO_MCP click requires approval (set CHICAGO_REQUIRE_APPROVAL=false to override)'}
        if not _GUI_OK:
            return {'error': 'pyautogui not installed'}
        pyautogui.click(x, y)
        action = {'action': 'click', 'x': x, 'y': y}
        self.action_log.append(action)
        return action

    def type_text(self, text: str) -> dict:
        if _REQUIRE_APPROVAL:
            return {'blocked': True, 'reason': 'CHICAGO_MCP type requires approval'}
        if not _GUI_OK:
            return {'error': 'pyautogui not installed'}
        pyautogui.typewrite(text, interval=0.05)
        action = {'action': 'type', 'text': text[:50]}
        self.action_log.append(action)
        return action

    def move(self, x: int, y: int) -> dict:
        if not _GUI_OK:
            return {'error': 'pyautogui not installed'}
        pyautogui.moveTo(x, y)
        return {'action': 'move', 'x': x, 'y': y}

    def to_dict(self) -> dict:
        return {'session_id': self.session_id, 'action_count': len(self.action_log)}


_sessions: dict[str, ComputerUseSession] = {}


def get_session(session_id: str) -> ComputerUseSession:
    if session_id not in _sessions:
        _sessions[session_id] = ComputerUseSession(session_id)
    return _sessions[session_id]

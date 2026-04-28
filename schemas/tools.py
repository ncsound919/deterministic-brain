from __future__ import annotations
from typing import Any, Dict, Literal, TypedDict

class ToolSpec(TypedDict, total=False):
    name: str
    description: str
    category: Literal['code', 'browser', 'data', 'system']
    schema: Dict[str, Any]

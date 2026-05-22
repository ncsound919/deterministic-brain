
import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

BOOKBRIDGE_URL = "http://127.0.0.1:8777"

def bookbridge_search(query: str, max_results: int = 5, include_equations: bool = False) -> Dict[str, Any]:
    """Search the personal book library for knowledge and equations."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/search",
            json={
                "query": query,
                "max_results": max_results,
                "include_equations": include_equations
            },
            timeout=10
        )
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge search failed: {e}")
        return {"error": str(e)}

def bookbridge_retrieve(book_id: str, page_start: int, page_end: int) -> Dict[str, Any]:
    """Retrieve full text for a specific page range from a book."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/retrieve",
            json={
                "book_id": book_id,
                "page_start": page_start,
                "page_end": page_end
            },
            timeout=15
        )
        # Note: If it's a streaming response in the actual server, we might need to collect it
        return {"content": resp.text}
    except Exception as e:
        logger.error(f"BookBridge retrieve failed: {e}")
        return {"error": str(e)}

def bookbridge_reading_plan(topic: str, goal: str = "") -> Dict[str, Any]:
    """Generate a prioritized reading plan for a research topic."""
    try:
        resp = requests.post(
            f"{BOOKBRIDGE_URL}/reading_plan",
            json={"topic": topic, "goal": goal},
            timeout=20
        )
        return resp.json()
    except Exception as e:
        logger.error(f"BookBridge reading plan failed: {e}")
        return {"error": str(e)}

def bookbridge_status() -> Dict[str, Any]:
    """Check BookBridge server health and index stats."""
    try:
        resp = requests.get(f"{BOOKBRIDGE_URL}/health", timeout=2)
        return resp.json()
    except Exception:
        return {"status": "offline"}

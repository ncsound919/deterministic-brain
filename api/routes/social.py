"""Social API — Handles social media scheduling and posting."""
from __future__ import annotations
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks

from features.social_posting import crosspost

router = APIRouter(prefix="/social", tags=["social"])
logger = logging.getLogger(__name__)

# In-memory queue for demo purposes
_post_queue: List[Dict[str, Any]] = []
_posted: List[Dict[str, Any]] = []

@router.get("/posts")
def get_posts() -> Dict:
    """Return all queued and completed posts."""
    all_posts = _post_queue + _posted
    return {"status": "ok", "posts": all_posts}

@router.post("/schedule")
def schedule_post(platform: str, content: str, delay_minutes: int, background_tasks: BackgroundTasks) -> Dict:
    """Schedule a post to be executed via Playwright."""
    post_job = {
        "platform": platform,
        "content": content,
        "delay": delay_minutes,
        "status": "pending"
    }
    
    if delay_minutes <= 0:
        # Execute immediately
        background_tasks.add_task(_execute_post, post_job)
        post_job["status"] = "processing"
    
    _post_queue.append(post_job)
    return {"status": "ok", "message": f"Post scheduled for {platform}"}

@router.post("/post-due")
def post_due(background_tasks: BackgroundTasks) -> Dict:
    """Trigger processing of due posts in the queue."""
    due_posts = [p for p in _post_queue if p["status"] == "pending"]
    for p in due_posts:
        p["status"] = "processing"
        background_tasks.add_task(_execute_post, p)
    return {"status": "ok", "message": f"Processing {len(due_posts)} due posts."}

def _execute_post(job: Dict[str, Any]):
    """Background task to run the browser automation."""
    try:
        res = crosspost(content=job["content"], platforms=[job["platform"]], headless=True)
        job["status"] = "posted"
        job["result"] = res
        if job in _post_queue:
            _post_queue.remove(job)
            _posted.append(job)
    except Exception as e:
        logger.error(f"Failed to post to {job['platform']}: {e}")
        job["status"] = "failed"
        job["error"] = str(e)

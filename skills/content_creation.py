from pydantic import BaseModel
from typing import Dict, Any, Optional
from loguru import logger
from schemas.schema_registry import SchemaRegistry
from orchestration.intent_router import IntentRouter
import json
import os

class ContentCreationRequest(BaseModel):
    """Schema for Content Creation Engine requests."""
    topic: str
    format: str = "podcast" # podcast, video, blog
    schedule_cron: Optional[str] = None # e.g. "0 9 * * *"
    
SchemaRegistry.register("content_creation", ContentCreationRequest)

def schedule_cron_job(task_payload: dict, cron_expression: str):
    """Registers the content task into the engine's cron schedule."""
    cron_file = ".cron_schedule.json"
    data = {"tasks": {}}
    if os.path.exists(cron_file):
        with open(cron_file, 'r') as f:
            try:
                data = json.load(f)
            except Exception:
                pass
            
    if "tasks" not in data:
        data["tasks"] = {}
        
    task_id = f"content_creation_{task_payload.get('topic', 'task').replace(' ', '_').lower()}"
    data["tasks"][task_id] = {
        "name": task_id,
        "skill": "content_creation",
        "trigger_type": "cron",
        "cron_expr": cron_expression,
        "inputs": task_payload,
        "enabled": True,
        "description": f"Auto-scheduled content creation for: {task_payload.get('topic')}"
    }
    
    with open(cron_file, 'w') as f:
        json.dump(data, f, indent=4)
        
    logger.info(f"Scheduled content creation task with cron: {cron_expression}")

def handle_content_creation(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handler for Content Creation workflows."""
    logger.info("Handling Content Creation Engine workflow...")
    
    # Deterministic parsing mock
    import re
    topic = "Default Topic"
    format_type = "podcast"
    cron = None
    
    topic_match = re.search(r'(?:about|topic)\s+([a-zA-Z0-9_\-\s]+)', query, re.IGNORECASE)
    if topic_match:
        topic = topic_match.group(1).strip()
        
    if "video" in query.lower():
        format_type = "video"
    elif "blog" in query.lower():
        format_type = "blog"
        
    cron_match = re.search(r'every\s+(day|week|month)', query, re.IGNORECASE)
    if cron_match:
        freq = cron_match.group(1).lower()
        if freq == "day": cron = "0 9 * * *"
        elif freq == "week": cron = "0 9 * * 1"
        elif freq == "month": cron = "0 9 1 * *"
        
    payload = {
        "topic": topic,
        "format": format_type,
        "schedule_cron": cron
    }
    
    try:
        validated_req = SchemaRegistry.validate_and_parse("content_creation", payload)
        
        if validated_req.schedule_cron:
            schedule_cron_job(validated_req.model_dump(), validated_req.schedule_cron)
            action = "scheduled_daemon_task"
        else:
            action = "triggering_content_engine_async"
            
        return {
            "status": "success",
            "action_taken": action,
            "topic": validated_req.topic,
            "format": validated_req.format,
            "scheduled": bool(validated_req.schedule_cron)
        }
        
    except ValueError as e:
        logger.error(f"Schema validation failed: {e}")
        return {"status": "failed", "reason": str(e)}

def register_content_creation_skill(intent_router: IntentRouter):
    keywords = [
        "content creation", "generate podcast", "create video", 
        "write blog", "hood alchemy", "content engine"
    ]
    intent_router.register_intent(
        intent_name="content_creation",
        keywords=keywords,
        handler=handle_content_creation
    )
    logger.info("Content Creation skill wrapped and registered.")

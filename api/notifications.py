"""
NOTIFICATIONS API - Real-time notifications for job completion, system events
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import os

router = APIRouter(prefix="/notifications", tags=["notifications"])

class Notification(BaseModel):
    id: str
    title: str
    message: str
    category: str  # job, system, alert, success
    timestamp: str
    read: bool = False
    details: Optional[Dict[str, Any]] = None

# In-memory notification store
_notifications: List[Notification] = []
_notification_id = 0

def add_notification(title: str, message: str, category: str = "system", details: Dict = None):
    """Add a notification to the queue"""
    global _notification_id, _notifications
    _notification_id += 1
    
    notification = Notification(
        id=str(_notification_id),
        title=title,
        message=message,
        category=category,
        timestamp=datetime.now().isoformat(),
        read=False,
        details=details
    )
    _notifications.append(notification)
    
    # Keep last 100 notifications
    if len(_notifications) > 100:
        _notifications = _notifications[-100:]
    
    return notification


@router.get("")
def get_notifications(limit: int = 20, unread_only: bool = False):
    """Get all notifications"""
    notifications = _notifications
    
    if unread_only:
        notifications = [n for n in notifications if not n.read]
    
    return {
        "notifications": notifications[-limit:],
        "total": len(_notifications),
        "unread": len([n for n in _notifications if not n.read])
    }


@router.get("/unread-count")
def get_unread_count():
    """Get count of unread notifications"""
    return {
        "unread": len([n for n in _notifications if not n.read]),
        "total": len(_notifications)
    }


@router.post("/{notification_id}/read")
def mark_as_read(notification_id: str):
    """Mark a notification as read"""
    for n in _notifications:
        if n.id == notification_id:
            n.read = True
            return {"status": "ok", "id": notification_id}
    raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all")
def mark_all_read():
    """Mark all notifications as read"""
    for n in _notifications:
        n.read = True
    return {"status": "ok", "marked": len(_notifications)}


@router.delete("/{notification_id}")
def delete_notification(notification_id: str):
    """Delete a notification"""
    global _notifications
    _notifications = [n for n in _notifications if n.id != notification_id]
    return {"status": "ok", "deleted": notification_id}


@router.get("/categories")
def get_categories():
    """Get notification counts by category"""
    categories = {}
    for n in _notifications:
        categories[n.category] = categories.get(n.category, 0) + 1
    return categories
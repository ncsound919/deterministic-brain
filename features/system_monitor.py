"""
SYSTEM MONITOR - Real-time dashboard with notifications
Shows all running processes, job status, and system health
"""
import time
import json
import threading
import os
from datetime import datetime
from pathlib import Path

class SystemMonitor:
    """Real-time system monitoring with notification queue"""
    
    def __init__(self):
        self.events = []
        self.notifications = []
        self.job_history = []
        self.metrics = {
            "jobs_run_today": 0,
            "jobs_succeeded": 0,
            "jobs_failed": 0,
            "uptime_start": time.time(),
            "last_activity": None
        }
        
    def log_event(self, category, message, status="info", details=None):
        """Log a system event"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "message": message,
            "status": status,  # info, success, warning, error
            "details": details or {}
        }
        self.events.append(event)
        
        # Keep last 100 events
        if len(self.events) > 100:
            self.events = self.events[-100:]
            
        # Add to notifications
        self.notifications.append(event)
        if len(self.notifications) > 50:
            self.notifications = self.notifications[-50:]
            
        print(f"[{category.upper()}] {message}")
        
    def record_job(self, job_name, status, output=None, error=None):
        """Record job execution"""
        job = {
            "timestamp": datetime.now().isoformat(),
            "name": job_name,
            "status": status,  # success, failed, running
            "output": str(output)[:200] if output else None,
            "error": str(error)[:100] if error else None
        }
        self.job_history.append(job)
        
        # Update metrics
        if status == "success":
            self.metrics["jobs_succeeded"] += 1
            self.metrics["jobs_run_today"] += 1
            self.log_event("JOB", f"Completed: {job_name}", "success", {"output": str(output)[:100]})
        elif status == "failed":
            self.metrics["jobs_failed"] += 1
            self.metrics["jobs_run_today"] += 1
            self.log_event("JOB", f"Failed: {job_name}", "error", {"error": str(error)[:100]})
            
        # Keep last 200 jobs
        if len(self.job_history) > 200:
            self.job_history = self.job_history[-200:]
    
    def get_status(self):
        """Get current system status"""
        uptime_seconds = time.time() - self.metrics["uptime_start"]
        
        return {
            "status": "OPERATIONAL",
            "uptime_seconds": int(uptime_seconds),
            "uptime_hours": round(uptime_seconds / 3600, 1),
            "metrics": self.metrics,
            "active_jobs": len([j for j in self.job_history if j["status"] == "running"]),
            "recent_events": self.events[-10:],
            "recent_notifications": self.notifications[-5:]
        }
    
    def get_dashboard_data(self):
        """Get data for dashboard display"""
        return {
            "system": {
                "status": "ONLINE",
                "version": "2.5.0",
                "mode": "24/7 Autonomous"
            },
            "metrics": {
                "total_jobs_run": len(self.job_history),
                "jobs_today": self.metrics["jobs_run_today"],
                "success_rate": round(self.metrics["jobs_succeeded"] / max(1, self.metrics["jobs_succeeded"] + self.metrics["jobs_failed"]) * 100, 1)
            },
            "jobs": self.job_history[-20:],
            "events": self.events[-30:],
            "notifications": self.notifications[-10:]
        }
    
    def save_state(self):
        """Save state to disk for recovery"""
        state = {
            "metrics": self.metrics,
            "job_history": self.job_history[-50:]
        }
        with open(".system_monitor_state.json", "w") as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load state from disk"""
        if os.path.exists(".system_monitor_state.json"):
            try:
                with open(".system_monitor_state.json") as f:
                    state = json.load(f)
                    self.metrics.update(state.get("metrics", {}))
                    self.job_history = state.get("job_history", [])
            except:
                pass


# Global monitor instance
monitor = SystemMonitor()
monitor.load_state()

def get_monitor():
    return monitor
"""Notification Service — Email and webhook notifications."""
from __future__ import annotations
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.deterministic-brain/notifications.json")


@dataclass
class NotificationConfig:
    """Notification configuration."""
    email: Optional[Dict[str, str]] = None
    webhook: Optional[Dict[str, str]] = None


class NotificationService:
    """Service for sending email and webhook notifications."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self._sent_history: List[Dict[str, Any]] = []

    def _load_config(self, config_path: Optional[str]) -> NotificationConfig:
        """Load notification config from file or environment."""
        path = config_path or os.environ.get("NOTIFICATION_CONFIG", DEFAULT_CONFIG_PATH)
        
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                return NotificationConfig(
                    email=data.get("email"),
                    webhook=data.get("webhook")
                )
            except Exception as e:
                logger.warning(f"Failed to load notification config: {e}")
        
        return NotificationConfig()

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Send an email notification.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body
        
        Returns:
            True if sent successfully
        """
        if not self.config.email:
            logger.warning("Email not configured, skipping")
            return False
        
        try:
            smtp_config = self.config.email
            msg = MIMEMultipart()
            msg["From"] = smtp_config.get("from_address", "deterministic-brain@local")
            msg["To"] = to_address
            msg["Subject"] = subject
            
            msg.attach(MIMEText(body, "plain"))
            
            host = smtp_config.get("smtp_host", "localhost")
            port = int(smtp_config.get("smtp_port", 25))
            
            with smtplib.SMTP(host, port) as server:
                if smtp_config.get("username"):
                    server.login(smtp_config["username"], smtp_config["password"])
                server.sendmail(msg["From"], [to_address], msg.as_string())
            
            self._sent_history.append({
                "type": "email",
                "to": to_address,
                "subject": subject,
                "timestamp": str(datetime.now())
            })
            
            logger.info(f"Email sent to {to_address}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_webhook(self, url: str, payload: Dict[str, Any]) -> bool:
        """Send a webhook notification.
        
        Args:
            url: Webhook URL
            payload: JSON payload to send
        
        Returns:
            True if sent successfully
        """
        if not self.config.webhook and not url:
            logger.warning("Webhook not configured, skipping")
            return False
        
        try:
            import requests
            
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code >= 200 and response.status_code < 300:
                self._sent_history.append({
                    "type": "webhook",
                    "url": url,
                    "payload": payload,
                    "timestamp": str(datetime.now())
                })
                logger.info(f"Webhook sent to {url}")
                return True
            else:
                logger.warning(f"Webhook returned {response.status_code}")
                return False
                
        except ImportError:
            logger.warning("requests not installed, skipping webhook")
            return False
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False

    def notify_task_complete(self, task_name: str, skill: str, 
                            status: str, output: str,
                            notify_email: Optional[str] = None,
                            notify_webhook: Optional[str] = None) -> None:
        """Notify on task completion.
        
        Args:
            task_name: Name of the completed task
            skill: Skill that was executed
            status: Task status (success/error)
            output: Task output summary
            notify_email: Optional email override
            notify_webhook: Optional webhook override
        """
        subject = f"Task {status}: {task_name}"
        body = f"""Task: {task_name}
Skill: {skill}
Status: {status}

Output:
{output[:500]}
"""
        
        email_target = notify_email or self.config.email.get("default_recipient") if self.config.email else None
        if email_target:
            self.send_email(email_target, subject, body)
        
        webhook_target = notify_webhook or self.config.webhook.get("default_url") if self.config.webhook else None
        if webhook_target:
            payload = {
                "task": task_name,
                "skill": skill,
                "status": status,
                "output": output[:500],
                "timestamp": str(datetime.now())
            }
            self.send_webhook(webhook_target, payload)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get notification history."""
        return self._sent_history.copy()

    def clear_history(self) -> None:
        """Clear notification history."""
        self._sent_history.clear()


_global_service: Optional[NotificationService] = None


def get_notification_service(config_path: Optional[str] = None) -> NotificationService:
    """Get or create global notification service."""
    global _global_service
    if _global_service is None:
        _global_service = NotificationService(config_path)
    return _global_service


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Convenience function to send email."""
    service = get_notification_service()
    return service.send_email(to_address, subject, body)


def send_webhook(url: str, payload: Dict[str, Any]) -> bool:
    """Convenience function to send webhook."""
    service = get_notification_service()
    return service.send_webhook(url, payload)
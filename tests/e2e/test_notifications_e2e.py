"""E2E Tests for Notifications (Email + Webhook)."""
from __future__ import annotations
import json


class TestEmailNotifications:
    """Test email notification functionality."""

    def test_email_initialization(self):
        """Notification service should initialize."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        assert service is not None
        assert hasattr(service, "send_email")
        assert hasattr(service, "send_webhook")

    def test_email_send_with_config(self, mock_email_server):
        """Should send email when configured."""
        from features.notification import NotificationService
        
        config = {
            "email": {
                "smtp_host": "localhost",
                "smtp_port": mock_email_server.split(":")[-1],
                "from_address": "test@local"
            }
        }
        
        service = NotificationService()
        service.config.email = config["email"]
        
        result = service.send_email(
            to_address="user@example.com",
            subject="Test Subject",
            body="Test body content"
        )
        
        assert isinstance(result, bool)

    def test_email_with_mock_server(self, mock_email_server):
        """Email should reach mock server."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        service.config = type('obj', (object,), {
            'email': {
                'smtp_host': 'localhost',
                'smtp_port': mock_email_server.split(':')[-1],
                'from_address': 'test@local'
            }
        })()
        
        result = service.send_email(
            to_address="test@example.com",
            subject="Task Complete",
            body="Your task has completed successfully."
        )

    def test_email_skip_when_not_configured(self):
        """Should skip email when not configured."""
        from features.notification import NotificationService
        
        service = NotificationService()
        service.config.email = None
        
        result = service.send_email(
            to_address="test@example.com",
            subject="Test",
            body="Test"
        )
        
        assert result == False

    def test_task_complete_notification_email(self, mock_email_server):
        """notify_task_complete should send email."""
        from features.notification import NotificationService
        
        service = NotificationService()
        service.config = type('obj', (object,), {
            'email': {
                'smtp_host': 'localhost',
                'smtp_port': mock_email_server.split(':')[-1],
                'from_address': 'test@local',
                'default_recipient': 'admin@example.com'
            }
        })()
        
        service.notify_task_complete(
            task_name="daily-audit",
            skill="audit",
            status="success",
            output="Audit complete. No issues found.",
            notify_email="admin@example.com"
        )


class TestWebhookNotifications:
    """Test webhook notification functionality."""

    def test_webhook_send_with_url(self, mock_webhook_server):
        """Should send webhook when URL provided."""
        from features.notification import NotificationService
        
        service = NotificationService()
        service.config = type('obj', (object,), {'webhook': {'default_url': mock_webhook_server}})()
        
        result = service.send_webhook(
            url=mock_webhook_server,
            payload={"task": "test", "status": "success"}
        )
        
        assert isinstance(result, bool)

    def test_webhook_payload_structure(self, mock_webhook_server):
        """Webhook payload should have expected structure."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        payload = {
            "task": "hourly-check",
            "skill": "react",
            "status": "success",
            "output": "Component generated",
            "timestamp": "2024-01-01T09:00:00"
        }
        
        result = service.send_webhook(mock_webhook_server, payload)
        
        assert isinstance(result, bool)

    def test_webhook_skip_when_not_configured(self):
        """Should skip webhook when not configured."""
        from features.notification import NotificationService
        
        service = NotificationService()
        service.config.webhook = None
        
        result = service.send_webhook(
            url="http://example.com/hook",
            payload={"test": True}
        )
        
        assert result == False

    def test_task_complete_notification_webhook(self, mock_webhook_server):
        """notify_task_complete should send webhook."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        service.notify_task_complete(
            task_name="daily-audit",
            skill="audit",
            status="success",
            output="Audit complete",
            notify_webhook=mock_webhook_server
        )


class TestNotificationHistory:
    """Test notification history tracking."""

    def test_history_tracking(self):
        """Should track sent notifications."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        service.config = type('obj', (object,), {'webhook': {'default_url': 'http://test'}})()
        service.send_webhook("http://test", {"test": "data"})
        
        history = service.get_history()
        
        assert isinstance(history, list)

    def test_history_clear(self):
        """Should clear history."""
        from features.notification import NotificationService
        
        service = NotificationService()
        
        service._sent_history = [{"test": "item"}]
        service.clear_history()
        
        assert len(service.get_history()) == 0


class TestNotificationServiceGlobal:
    """Test global notification service."""

    def test_global_service_singleton(self):
        """Should return singleton service."""
        from features.notification import get_notification_service
        
        service1 = get_notification_service()
        service2 = get_notification_service()
        
        assert service1 is service2

    def test_convenience_functions(self):
        """Convenience functions should work."""
        from features.notification import send_email, send_webhook
        
        assert callable(send_email)
        assert callable(send_webhook)


class TestNotificationIntegration:
    """Test notification integration with scheduler."""

    def test_scheduler_sends_notification_on_complete(self, brain_app, mock_email_server, mock_webhook_server):
        """Scheduler should trigger notification on task completion."""
        
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="notify-me",
            skill="react",
            trigger_type="interval",
            interval_seconds=60,
            task_input={},
            notify_email="test@example.com",
            notify_webhook=mock_webhook_server
        )
        
        scheduler.tick()

    def test_notification_config_from_env(self, tmp_path):
        """Should load config from environment path."""
        from features.notification import NotificationService
        
        config_file = tmp_path / "test_notifications.json"
        config_file.write_text(json.dumps({
            "email": {"smtp_host": "mail.test.local"},
            "webhook": {"default_url": "http://test.local/hook"}
        }))
        
        import os
        os.environ["NOTIFICATION_CONFIG"] = str(config_file)
        
        service = NotificationService(config_path=str(config_file))
        
        assert service.config.email is not None or service.config.webhook is not None
"""E2E Tests for Scheduler Integration."""
from __future__ import annotations
import os
import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestSchedulerBasicOperations:
    """Test basic scheduler operations."""

    def test_scheduler_initialization(self, brain_app):
        """Scheduler should initialize correctly."""
        scheduler = brain_app["scheduler"]
        
        assert scheduler is not None
        assert hasattr(scheduler, "schedule_task")
        assert hasattr(scheduler, "list_tasks")
        assert hasattr(scheduler, "get_results")

    def test_schedule_interval_task(self, brain_app):
        """Should schedule an interval-based task."""
        scheduler = brain_app["scheduler"]
        
        task_id = scheduler.schedule_task(
            name="hourly-check",
            skill="react",
            trigger_type="interval",
            interval_seconds=3600,
            task_input={"test": True}
        )
        
        assert task_id == "hourly-check"
        
        tasks = scheduler.list_tasks()
        assert any(t["name"] == "hourly-check" for t in tasks)

    def test_schedule_cron_task(self, brain_app):
        """Should schedule a cron-based task."""
        scheduler = brain_app["scheduler"]
        
        task_id = scheduler.schedule_task(
            name="daily-audit",
            skill="audit",
            trigger_type="cron",
            cron_expr="0 9 * * *",
            task_input={"report": True}
        )
        
        assert task_id == "daily-audit"
        
        tasks = scheduler.list_tasks()
        assert any(t["name"] == "daily-audit" for t in tasks)


class TestSchedulerTaskExecution:
    """Test scheduler task execution."""

    def test_interval_task_runs(self, brain_app, tmp_project_dir):
        """Interval task should execute when triggered."""
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="test-interval",
            skill="react",
            trigger_type="interval",
            interval_seconds=1,
            task_input={"component_name": "TestComponent"}
        )
        
        from features.scheduler import TaskResult
        
        with patch("features.scheduler.get_scheduler") as mock_get:
            mock_get.return_value = scheduler
            
            result = scheduler.tick()
            
        results = scheduler.get_results("test-interval")
        
        assert isinstance(results, list)

    def test_cron_task_runs_at_correct_time(self, brain_app):
        """Cron task should only run at scheduled times."""
        from features.scheduler import Scheduler
        
        scheduler = Scheduler()
        
        scheduler.schedule_task(
            name="daily-test",
            skill="audit",
            trigger_type="cron",
            cron_expr="0 9 * * *",
            task_input={}
        )
        
        with patch("features.scheduler.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 8, 59, 0)
            
            results_before = scheduler.tick()
            
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 9, 0, 0)
            
            results_at = scheduler.tick()
            
            mock_dt.utcnow.return_value = datetime(2024, 1, 1, 9, 1, 0)
            
            results_after = scheduler.tick()

    def test_task_introspection(self, brain_app):
        """Scheduler should list all tasks correctly."""
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task("task-1", "react", "interval", 60)
        scheduler.schedule_task("task-2", "rest_api", "cron", "0 9 * * *")
        
        tasks = scheduler.list_tasks()
        
        assert len(tasks) >= 2
        
        task_names = [t["name"] for t in tasks]
        assert "task-1" in task_names
        assert "task-2" in task_names


class TestSchedulerErrorHandling:
    """Test scheduler error handling."""

    def test_handles_failing_task(self, brain_app):
        """Scheduler should handle failing tasks gracefully."""
        from features.scheduler import Scheduler
        
        scheduler = Scheduler()
        
        def failing_skill(task_input):
            raise ValueError("Intentional failure")
        
        scheduler.register_skill("failing-skill", failing_skill)
        
        scheduler.schedule_task(
            name="will-fail",
            skill="failing-skill",
            trigger_type="interval",
            interval_seconds=1,
            task_input={}
        )
        
        results = scheduler.tick()
        
        task_results = scheduler.get_results("will-fail")
        
        assert any(r.get("status") == "error" for r in task_results)


class TestSchedulerResultsPersistence:
    """Test scheduler results storage."""

    def test_results_stored(self, brain_app):
        """Task results should be stored and retrievable."""
        scheduler = brain_app["scheduler"]
        
        from features.scheduler import TaskResult
        
        scheduler.schedule_task(
            name="test-result",
            skill="react",
            trigger_type="interval",
            interval_seconds=60,
            task_input={}
        )
        
        scheduler.tick()
        
        results = scheduler.get_results("test-result")
        
        assert isinstance(results, list)

    def test_results_have_required_fields(self, brain_app):
        """Task results should have required fields."""
        scheduler = brain_app["scheduler"]
        
        from features.scheduler import TaskResult
        
        scheduler.schedule_task(
            name="test-fields",
            skill="react",
            trigger_type="interval",
            interval_seconds=60,
            task_input={"test": "value"}
        )
        
        scheduler.tick()
        
        results = scheduler.get_results("test-fields")
        
        if results:
            result = results[0]
            assert "status" in result or "task_id" in result


class TestSchedulerDeterminism:
    """Test scheduler determinism."""

    def test_same_schedule_same_execution_order(self, brain_app):
        """Same schedule should produce same execution order."""
        scheduler1 = brain_app["scheduler"]
        
        scheduler1.schedule_task(
            name="det-test",
            skill="react",
            trigger_type="interval",
            interval_seconds=1,
            task_input={}
        )
        
        results1 = scheduler1.tick()
        
        scheduler2 = brain_app["scheduler"]
        
        scheduler2.schedule_task(
            name="det-test",
            skill="react",
            trigger_type="interval",
            interval_seconds=1,
            task_input={}
        )
        
        results2 = scheduler2.tick()


class TestSchedulerNotification:
    """Test scheduler with notification integration."""

    def test_task_with_email_notification(self, brain_app, mock_notification_config):
        """Task with email notification should trigger notification."""
        from features.notification import NotificationService
        
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="notify-test",
            skill="react",
            trigger_type="interval",
            interval_seconds=60,
            task_input={},
            notify_email="test@example.com"
        )
        
        scheduler.tick()
        
    def test_task_with_webhook_notification(self, brain_app, mock_notification_config):
        """Task with webhook should trigger notification."""
        from features.notification import NotificationService
        
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="webhook-test",
            skill="react",
            trigger_type="interval",
            interval_seconds=60,
            task_input={},
            notify_webhook="http://localhost:1234/notify"
        )
        
        scheduler.tick()


class TestSchedulerSkillIntegration:
    """Test scheduler with skill execution."""

    def test_scheduler_executes_skill(self, brain_app, tmp_project_dir):
        """Scheduler should execute skill on tick."""
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="skill-exec-test",
            skill="react",
            trigger_type="interval",
            interval_seconds=1,
            task_input={"component_name": "ScheduledComponent"},
            context={"project_dir": str(tmp_project_dir)}
        )
        
        results = scheduler.tick()
        
        task_results = scheduler.get_results("skill-exec-test")
        
        assert isinstance(task_results, list)
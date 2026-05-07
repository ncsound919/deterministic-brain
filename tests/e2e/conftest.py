"""E2E Test Fixtures and Configuration."""
from __future__ import annotations
import os
import sys
import json
import shutil
import tempfile
import threading
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Create a temporary project directory for skill outputs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "docs").mkdir()
    
    (project_dir / "src" / "main.py").write_text("# Main entry point\ndef main():\n    pass\n")
    (project_dir / "src" / "utils.py").write_text("# Utility functions\n")
    (project_dir / "tests" / "test_basic.py").write_text("def test_example():\n    assert True\n")
    (project_dir / "README.md").write_text("# Sample Project\n")
    
    return project_dir


@pytest.fixture
def brain_app(tmp_project_dir):
    """Initialize the brain application with all components."""
    import random
    random.seed(42)
    
    os.environ["TEST_MODE"] = "1"
    os.environ["PROJECT_ROOT"] = str(tmp_project_dir)
    
    from brain.task_parser import TaskParser
    from brain.router import MoERouter
    from orchestration.dca_engine import DeterministicCodingAgent
    from features.scheduler import Scheduler
    
    parser = TaskParser()
    router = MoERouter()
    agent = DeterministicCodingAgent()
    scheduler = Scheduler()
    
    return {
        "parser": parser,
        "router": router,
        "agent": agent,
        "scheduler": scheduler,
        "project_dir": tmp_project_dir,
    }


class MockEmailHandler(BaseHTTPRequestHandler):
    """Mock email server handler."""
    sent_emails = []
    
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        MockEmailHandler.sent_emails.append(json.loads(body))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "sent"}')


@pytest.fixture
def mock_email_server():
    """Start a mock SMTP server for email testing."""
    server = HTTPServer(('localhost', 0), MockEmailHandler)
    server_port = server.server_address[1]
    
    MockEmailHandler.sent_emails.clear()
    
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    
    yield f"http://localhost:{server_port}"
    
    server.server_close()
    thread.join(timeout=1)


class MockWebhookHandler(BaseHTTPRequestHandler):
    """Mock webhook server handler."""
    received_payloads = []
    
    def log_message(self, format, *args):
        pass
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        MockWebhookHandler.received_payloads.append(json.loads(body))
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "received"}')


@pytest.fixture
def mock_webhook_server():
    """Start a mock webhook server for phone notifications."""
    server = HTTPServer(('localhost', 0), MockWebhookHandler)
    server_port = server.server_address[1]
    
    MockWebhookHandler.received_payloads.clear()
    
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    
    yield f"http://localhost:{server_port}"
    
    server.server_close()
    thread.join(timeout=1)


@pytest.fixture
def mock_notification_config(mock_email_server, mock_webhook_server, tmp_path):
    """Create notification config with mock endpoints."""
    config = {
        "email": {
            "smtp_host": "localhost",
            "smtp_port": mock_email_server.split(":")[-1],
            "from_address": "test@deterministic-brain.local",
        },
        "webhook": {
            "url": mock_webhook_server,
        }
    }
    
    config_file = tmp_path / "notifications.json"
    config_file.write_text(json.dumps(config))
    
    os.environ["NOTIFICATION_CONFIG"] = str(config_file)
    
    return config_file


@pytest.fixture
def test_seed():
    """Return a fixed seed for deterministic tests."""
    return 42


@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test."""
    import random
    random.seed(42)
    yield
    random.seed(42)


@pytest.fixture
def sample_repo(tmp_project_dir):
    """Create a sample repository for repo-audit tests."""
    (tmp_project_dir / "src" / "app.py").write_text("""
import os
def run():
    os.system('echo hello')
    
if __name__ == '__main__':
    run()
""")
    (tmp_project_dir / "requirements.txt").write_text("requests==2.28.0\nflask==2.0.0\n")
    (tmp_project_dir / ".env").write_text("SECRET_KEY=dev-secret-key\n")
    
    return tmp_project_dir


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "determinism: mark test as determinism test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
"""Tests for the acquisition API routes."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

app = FastAPI()
from api.routes.acquisition import router as acquisition_router
app.include_router(acquisition_router)

client = TestClient(app)


class TestAcquisitionAPI:
    def test_get_status(self):
        resp = client.get("/api/acquisition/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "tracker_dir" in data
        assert "files_present" in data

    def test_get_daily_log(self):
        resp = client.get("/api/acquisition/daily-log")
        assert resp.status_code == 200
        data = resp.json()
        assert "content" in data

    def test_get_progress(self):
        resp = client.get("/api/acquisition/progress")
        assert resp.status_code == 200

    def test_get_insights(self):
        resp = client.get("/api/acquisition/insights")
        assert resp.status_code == 200

    def test_get_metrics(self):
        resp = client.get("/api/acquisition/metrics")
        assert resp.status_code == 200

    def test_post_daily_log(self):
        resp = client.post("/api/acquisition/daily-log", json={
            "brain_state": "testing",
            "tasks_executed": 5,
        })
        assert resp.status_code == 200

    def test_post_insight(self):
        resp = client.post("/api/acquisition/insights", json={
            "signal_type": "test",
            "signal": "test signal",
            "implication": "test implication",
            "action": "test action",
        })
        assert resp.status_code == 200

    def test_post_metrics(self):
        resp = client.post("/api/acquisition/metrics", json={
            "scores": {"Test": 75.0},
        })
        assert resp.status_code == 200

    def test_post_progress(self):
        resp = client.post("/api/acquisition/progress", json={
            "assets": {
                "TestAsset": {
                    "deploy_readiness": "50%",
                    "build": False,
                    "tests": False,
                    "env": False,
                    "docker": False,
                }
            },
        })
        assert resp.status_code == 200

    def test_post_daily_log_shows_in_get(self):
        resp = client.post("/api/acquisition/daily-log", json={"brain_state": "live", "tasks_executed": 3})
        assert resp.status_code == 200
        resp2 = client.get("/api/acquisition/daily-log")
        assert resp2.status_code == 200
        assert "live" in resp2.json()["content"]

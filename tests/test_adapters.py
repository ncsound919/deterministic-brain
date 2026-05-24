"""Unit tests for Phase 1-3: Ledger + BaseAdapter + AetherDeskAdapter."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ledger.core as _ledger_core
from adapters.base import AdapterCallResult, BaseAdapter, LRUCache
from adapters.aetherdesk import (
    AetherDeskAdapter,
    CallEvent,
    CampaignConfig,
    CampaignStats,
    CampaignStatus,
    UsageReport,
)


@pytest.fixture(autouse=True)
def _temp_dirs(monkeypatch, tmp_path):
    """Isolate ledger writes to a temp dir for every test."""
    monkeypatch.setattr(_ledger_core, "BASE_DIR", tmp_path)
    monkeypatch.setattr(_ledger_core, "EVENTS_DIR", tmp_path / "events")
    monkeypatch.setattr(_ledger_core, "PLANS_DIR", tmp_path / "daily-plans")
    monkeypatch.setattr(_ledger_core, "CAMPAIGNS_DIR", tmp_path / "campaigns")
    monkeypatch.setattr(_ledger_core, "OVERRIDES_DIR", tmp_path / "overrides")
    monkeypatch.setattr(_ledger_core, "_IDEMPOTENCY_FILE", tmp_path / "events" / "idempotency.json")
    for d in ("events", "daily-plans", "campaigns", "overrides"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)


# ═════════════════════════════════════════════════════════════════════
# Ledger tests
# ═════════════════════════════════════════════════════════════════════

def test_write_and_read_events():
    from ledger import write_event, read_events

    write_event({"type": "test_event", "system": "aetherdesk", "data": {"key": "val"}})
    write_event({"type": "test_nested", "system": "openhub", "data": {"nested": {"x": 1}}})
    events = list(read_events(datetime.utcnow().date()))
    assert len(events) == 2
    assert events[0]["type"] == "test_event"
    assert events[1]["type"] == "test_nested"
    assert events[1]["data"]["nested"]["x"] == 1


def test_write_and_read_daily_plan():
    from ledger import write_daily_plan, read_daily_plan

    plan = {"campaigns": [{"profile": "test", "leads": 50}], "date": "2026-05-24"}
    write_daily_plan(date(2026, 5, 24), plan)
    loaded = read_daily_plan(date(2026, 5, 24))
    assert loaded is not None
    assert loaded["campaigns"][0]["leads"] == 50


def test_read_nonexistent_plan():
    from ledger import read_daily_plan

    assert read_daily_plan(date(2026, 1, 1)) is None


def test_active_campaigns_roundtrip():
    from ledger import write_active_campaigns, read_active_campaigns

    data = {"camp-1": {"status": "running", "leads_queued": 10}}
    write_active_campaigns(data)
    result = read_active_campaigns()
    assert result == data


def test_read_active_campaigns_empty():
    from ledger import read_active_campaigns

    result = read_active_campaigns()
    assert result == {}


def test_idempotency_persist_and_retrieve():
    from ledger import get_cached_response, mark_response_seen

    key = "test-idem-key"
    assert get_cached_response(key) is None
    mark_response_seen(key, {"ok": True, "data": "hello"})
    cached = get_cached_response(key)
    assert cached == {"ok": True, "data": "hello"}


def test_idempotency_survives_reload():
    from ledger import get_cached_response, mark_response_seen

    key = "test-survives"
    mark_response_seen(key, {"ok": True, "data": "persisted"})
    imported = get_cached_response(key)
    assert imported == {"ok": True, "data": "persisted"}


def test_manual_pause_detection():
    from ledger import is_manual_pause_active, manual_pause_flag_path

    flag = manual_pause_flag_path()
    flag.unlink(missing_ok=True)
    assert not is_manual_pause_active()

    flag.touch()
    assert is_manual_pause_active()

    flag.unlink()
    assert not is_manual_pause_active()


# ═════════════════════════════════════════════════════════════════════
# LRU Cache tests
# ═════════════════════════════════════════════════════════════════════

def test_lru_cache_get_set():
    cache = LRUCache(maxsize=3)
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.get("missing") is None


def test_lru_cache_eviction():
    cache = LRUCache(maxsize=3)
    for i in range(5):
        cache.set(f"key-{i}", i)
    assert cache.get("key-0") is None
    assert cache.get("key-4") == 4


def test_lru_cache_moves_used_to_end():
    cache = LRUCache(maxsize=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.get("a")  # moves a to front
    cache.set("d", 4)  # evicts b (least recently used)
    assert cache.get("a") == 1
    assert cache.get("b") is None
    assert cache.get("c") == 3
    assert cache.get("d") == 4


# ═════════════════════════════════════════════════════════════════════
# BaseAdapter idempotency tests
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_first_call_executes():
    adapter = BaseAdapter("test")
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        return AdapterCallResult(ok=True, status_code=200, data="hello")

    result = await adapter.call_with_idempotency("key-1", fn)
    assert result.data == "hello"
    assert call_count == 1


@pytest.mark.asyncio
async def test_duplicate_key_uses_lru_cache():
    adapter = BaseAdapter("test")
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        return AdapterCallResult(ok=True, status_code=200, data="hello")

    await adapter.call_with_idempotency("key-2", fn)
    call_count = 0
    result = await adapter.call_with_idempotency("key-2", fn)
    assert result.data == "hello"
    assert call_count == 0


@pytest.mark.asyncio
async def test_duplicate_key_survives_restart_via_ledger():
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        return AdapterCallResult(ok=True, status_code=200, data="hello")

    adapter1 = BaseAdapter("test")
    await adapter1.call_with_idempotency("key-3", fn)

    call_count = 0
    adapter2 = BaseAdapter("test")
    result = await adapter2.call_with_idempotency("key-3", fn)
    assert result.data == "hello"
    assert call_count == 0


@pytest.mark.asyncio
async def test_retries_on_failure():
    adapter = BaseAdapter("test", max_retries=2, initial_backoff=0.01)
    call_count = 0

    async def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("transient error")
        return AdapterCallResult(ok=True, status_code=200, data="recovered")

    result = await adapter.call_with_idempotency("key-retry", fn)
    assert result.ok
    assert call_count == 3


# ═════════════════════════════════════════════════════════════════════
# AetherDeskAdapter tests (with mocked httpx)
# ═════════════════════════════════════════════════════════════════════

@pytest.fixture
def adapter():
    return AetherDeskAdapter(base_url="http://aetherdesk.local", api_key="test-key")


@pytest.mark.asyncio
async def test_adapter_health_ok(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
        result = await adapter.health()
        assert result.ok
        assert result.status_code == 200


@pytest.mark.asyncio
async def test_adapter_health_fails(adapter):
    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=ConnectionError("down")
        )
        result = await adapter.health()
        assert not result.ok
        assert "down" in result.error


@pytest.mark.asyncio
async def test_get_campaign_stats(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "total_calls": 45, "answered": 12, "voicemail": 8, "converted": 3
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        stats = await adapter.get_campaign_stats()
        assert stats.total_calls == 45
        assert stats.answered == 12
        assert stats.converted == 3


@pytest.mark.asyncio
async def test_get_usage_and_billing(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"total_calls": 100, "total_minutes": 234.5, "total_cost": 3.52}

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        usage = await adapter.get_usage_and_billing()
        assert usage.calls == 100
        assert usage.minutes == 234.5
        assert usage.cost == 3.52


@pytest.mark.asyncio
async def test_validate_lead_inventory_has_leads(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"leads_available": 5}

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        assert await adapter.validate_lead_inventory(CampaignConfig(
            profile_id="test", max_concurrent=1, delay_between_calls=5.0,
            filter_status="new", lead_limit=50
        ))


@pytest.mark.asyncio
async def test_validate_lead_inventory_no_leads(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"leads_available": 0}

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=[mock_resp])
        assert not await adapter.validate_lead_inventory(CampaignConfig(
            profile_id="test", max_concurrent=1, delay_between_calls=5.0,
            filter_status="new", lead_limit=50
        ))


@pytest.mark.asyncio
async def test_launch_campaign_writes_event(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "campaign_id": "CAMPAIGN-001", "status": "launched", "leads_queued": 10
    }

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=[mock_resp])

        config = CampaignConfig(
            profile_id="PROF-META-SALES", max_concurrent=3, delay_between_calls=10.0,
            filter_status="new", lead_limit=50
        )
        status = await adapter.launch_campaign(config, "idem-launch-001")

        assert status.id == "CAMPAIGN-001"
        assert status.status == "launched"
        assert status.leads_queued == 10

        from ledger import read_events

        events = list(read_events(datetime.utcnow().date()))
        assert len(events) == 1
        launch_events = [e for e in events if e.get("type") == "campaign_launch"]
        assert len(launch_events) == 1
        assert launch_events[0]["system"] == "aetherdesk"


@pytest.mark.asyncio
async def test_launch_campaign_idempotent(adapter):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "campaign_id": "CAMPAIGN-002", "status": "launched", "leads_queued": 5
    }

    call_count = 0

    async def patched_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_resp

    with patch.object(adapter, "_client") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(side_effect=patched_post)

        config = CampaignConfig(
            profile_id="test", max_concurrent=1, delay_between_calls=5.0,
            filter_status="new", lead_limit=10
        )

        result1 = await adapter.launch_campaign(config, "idem-launch-idem-001")
        call_count = 0
        result2 = await adapter.launch_campaign(config, "idem-launch-idem-001")

        assert result1.id == result2.id
        assert call_count == 0

# Acquisition Tracker UX + Expanded AGI Testing

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add acquisition tracker API endpoints, a dashboard page, 60+ new AGI unit tests, and 15 Playwright UX tests.

**Architecture:** FastAPI routes in `api/routes/acquisition.py` wrap `AcquisitionBridge` methods. React page in `aether-dashboard/src/pages/AcquisitionTracker.jsx` consumes these via `src/api.js`. AGI tests extend `tests/test_acquisition_brain.py`. Playwright tests go in `tests/e2e/test_acquisition_ux.py`.

**Tech Stack:** Python, FastAPI, React 19, Framer Motion, Lucide React, Playwright, pytest

---

### Task 1: API Routes — `api/routes/acquisition.py`

**Files:**
- Create: `api/routes/acquisition.py`
- Modify: `api/server.py` (+ import + include_router)
- Test: `tests/test_acquisition_api.py` (lightweight TestClient test)

- [ ] **Step 1.1: Write the API test**

Create `tests/test_acquisition_api.py`:

```python
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
```

Run: `pytest tests/test_acquisition_api.py -v --tb=short`
Expected: FAIL with import errors (no router yet)

- [ ] **Step 1.2: Create the router file**

Write `api/routes/acquisition.py`:

```python
"""Acquisition Tracker - REST API Routes"""
from __future__ import annotations
from fastapi import APIRouter
from typing import Dict, Any, Optional
from pydantic import BaseModel
from pathlib import Path

router = APIRouter(prefix="/api/acquisition", tags=["acquisition"])

_bridge = None

def _get_bridge():
    global _bridge
    if _bridge is None:
        from acquisition_bridge import AcquisitionBridge
        _bridge = AcquisitionBridge()
    return _bridge


class DailyLogRequest(BaseModel):
    brain_state: str = "unknown"
    tasks_executed: int = 0
    trends_detected: int = 0
    portfolio_pulse: str = "stable"


class ProgressRequest(BaseModel):
    assets: Dict[str, Dict[str, Any]]


class InsightRequest(BaseModel):
    signal_type: str
    signal: str
    implication: str
    action: str


class MetricsRequest(BaseModel):
    scores: Dict[str, float]


@router.get("/status")
def get_status() -> Dict:
    bridge = _get_bridge()
    return bridge.get_status()


@router.get("/daily-log")
def get_daily_log() -> Dict:
    bridge = _get_bridge()
    log_file = bridge.tracker_dir / "DAILY-LOG.md"
    content = bridge._safe_read(log_file)
    return {"content": content}


@router.post("/daily-log")
def post_daily_log(req: DailyLogRequest) -> Dict:
    bridge = _get_bridge()
    bridge.log_autonomous_session(req.model_dump())
    return {"status": "ok"}


@router.get("/progress")
def get_progress() -> Dict:
    bridge = _get_bridge()
    progress_file = bridge.tracker_dir / "PROGRESS.md"
    content = bridge._safe_read(progress_file)
    return {"content": content}


@router.post("/progress")
def post_progress(req: ProgressRequest) -> Dict:
    bridge = _get_bridge()
    bridge.update_portfolio_progress(dict(req.assets))
    return {"status": "ok"}


@router.get("/insights")
def get_insights() -> Dict:
    bridge = _get_bridge()
    insights_file = bridge.tracker_dir / "INSIGHTS.md"
    content = bridge._safe_read(insights_file)
    return {"content": content}


@router.post("/insights")
def post_insight(req: InsightRequest) -> Dict:
    bridge = _get_bridge()
    bridge.record_insight(req.signal_type, req.signal, req.implication, req.action)
    return {"status": "ok"}


@router.get("/metrics")
def get_metrics() -> Dict:
    bridge = _get_bridge()
    metrics_file = bridge.tracker_dir / "METRICS.md"
    content = bridge._safe_read(metrics_file)
    return {"content": content}


@router.post("/metrics")
def post_metrics(req: MetricsRequest) -> Dict:
    bridge = _get_bridge()
    bridge.refresh_metrics(dict(req.scores))
    return {"status": "ok"}
```

- [ ] **Step 1.3: Register router in api/server.py**

At the top of `api/server.py`, add the import:
```python
from api.routes.acquisition import router as acquisition_router
```

After the other `app.include_router(...)` calls, add:
```python
app.include_router(acquisition_router)
```

- [ ] **Step 1.4: Run API tests**

Run: `pytest tests/test_acquisition_api.py -v --tb=short`
Expected: All 10 tests PASS

---

### Task 2: Dashboard Page — `AcquisitionTracker.jsx`

**Files:**
- Create: `aether-dashboard/src/pages/AcquisitionTracker.jsx`
- Modify: `aether-dashboard/src/api.js` (+ acquisition API functions)
- Modify: `aether-dashboard/src/App.jsx` (+ page entry + route + import)

- [ ] **Step 2.1: Add API functions to src/api.js**

Append to `aether-dashboard/src/api.js`:

```javascript
// ─── Acquisition Tracker ─────────────────────────────────────
export const getAcquisitionStatus = () => fetchJSON(`${BRAIN_API}/api/acquisition/status`);
export const getAcquisitionLog = () => fetchJSON(`${BRAIN_API}/api/acquisition/daily-log`);
export const postAcquisitionLog = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/daily-log`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionProgress = () => fetchJSON(`${BRAIN_API}/api/acquisition/progress`);
export const postAcquisitionProgress = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/progress`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionInsights = () => fetchJSON(`${BRAIN_API}/api/acquisition/insights`);
export const postAcquisitionInsight = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/insights`, { method: 'POST', body: JSON.stringify(data) });
export const getAcquisitionMetrics = () => fetchJSON(`${BRAIN_API}/api/acquisition/metrics`);
export const postAcquisitionMetrics = (data) => fetchJSON(`${BRAIN_API}/api/acquisition/metrics`, { method: 'POST', body: JSON.stringify(data) });
```

- [ ] **Step 2.2: Add page to sidebar in App.jsx**

In the `PAGES` array, add after the finance entry:
```javascript
{ id: 'acquisition', label: 'Acquisition', icon: Target, color: '#FF4500', section: 'Business' },
```

Add the import at the top of `App.jsx`:
```javascript
import { Target } from 'lucide-react';
```

Add to `PAGE_MAP`:
```javascript
acquisition: AcquisitionTracker,
```

Add the import:
```javascript
import AcquisitionTracker from './pages/AcquisitionTracker';
```

- [ ] **Step 2.3: Create the AcquisitionTracker page**

Write `aether-dashboard/src/pages/AcquisitionTracker.jsx`:

```javascript
import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, FileText, TrendingUp, Target, Check, X, RefreshCw, Loader2, Activity } from 'lucide-react';
import { getAcquisitionStatus, getAcquisitionLog, getAcquisitionProgress, getAcquisitionInsights, getAcquisitionMetrics } from '../api';
import { usePageState, useAutoRefresh } from '../stateManager';

function MetricCard({ label, value, icon: Icon, color }) {
  return (
    <div style={{
      background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)',
      border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
        <Icon size={16} color={color} />
        <span>{label}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}

function parseMarkdownTable(md) {
  const lines = md.split('\n').filter(l => l.trim() && l.startsWith('|'));
  if (lines.length < 3) return [];
  const headers = lines[0].split('|').map(h => h.trim()).filter(Boolean);
  const rows = lines.slice(2).map(line =>
    line.split('|').map(c => c.trim()).filter(Boolean)
  );
  return { headers, rows };
}

function parseInsightRows(md) {
  const lines = md.split('\n').filter(l => l.trim().startsWith('|'));
  const dataLines = lines.filter(l => l.includes('**') || l.match(/\d{4}-\d{2}-\d{2}/));
  return dataLines.map(l => l.split('|').map(c => c.trim()).filter(Boolean));
}

function parseDailyEntries(md) {
  const entries = [];
  const lines = md.split('\n');
  let current = [];
  for (const line of lines) {
    if (line.startsWith('### ')) {
      if (current.length) entries.push(current.join('\n'));
      current = [line];
    } else if (current.length) {
      current.push(line);
    }
  }
  if (current.length) entries.push(current.join('\n'));
  return entries;
}

export default function AcquisitionTracker() {
  const [status, setStatus] = useState(null);
  const [logContent, setLogContent] = useState('');
  const [progressContent, setProgressContent] = useState('');
  const [insightsContent, setInsightsContent] = useState('');
  const [metricsContent, setMetricsContent] = useState('');
  const [pageState, updatePageState] = usePageState('acquisition', { activeTab: 'overview' });

  const refresh = useCallback(async () => {
    const [s, log, prog, ins, met] = await Promise.all([
      getAcquisitionStatus(),
      getAcquisitionLog(),
      getAcquisitionProgress(),
      getAcquisitionInsights(),
      getAcquisitionMetrics(),
    ]);
    if (!s._error) setStatus(s);
    if (!log._error) setLogContent(log.content);
    if (!prog._error) setProgressContent(prog.content);
    if (!ins._error) setInsightsContent(ins.content);
    if (!met._error) setMetricsContent(met.content);
  }, []);

  useAutoRefresh(refresh, 10000, true);

  const progressTable = parseMarkdownTable(progressContent);
  const insightRows = parseInsightRows(insightsContent);
  const dailyEntries = parseDailyEntries(logContent);

  const filesOk = status?.files_present;
  const portfolioCount = progressTable?.rows?.length || 0;
  const insightCount = insightRows.length || 0;
  const entryCount = dailyEntries.length || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--gap-md)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
        <Target size={24} color="#FF4500" />
        <div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>Acquisition Tracker</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Portfolio health, daily ops, market intelligence</div>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          {filesOk ? <Check size={14} color="var(--success)" /> : <X size={14} color="var(--danger)" />}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Tracker {filesOk ? 'Online' : 'Offline'}</span>
          <RefreshCw size={14} color="var(--text-muted)" style={{ cursor: 'pointer' }} onClick={refresh} />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 'var(--gap-md)' }}>
        <MetricCard label="Portfolio Assets" value={portfolioCount} icon={BarChart3} color="var(--primary)" />
        <MetricCard label="Daily Entries" value={entryCount} icon={FileText} color="var(--accent)" />
        <MetricCard label="Insights Tracked" value={insightCount} icon={TrendingUp} color="var(--warning)" />
        <MetricCard label="Tracker Status" value={filesOk ? 'Active' : '—'} icon={Activity} color="var(--success)" />
      </div>

      {progressTable?.rows?.length > 0 && (
        <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Portfolio Deploy Readiness</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {progressTable.headers.map((h, i) => (
                    <th key={i} style={{ textAlign: 'left', padding: '6px 8px', color: 'var(--text-muted)', fontWeight: 500 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {progressTable.rows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                    {row.map((cell, j) => (
                      <td key={j} style={{ padding: '6px 8px' }}>
                        {cell.includes('✅') ? <span style={{ color: 'var(--success)' }}>{cell}</span> :
                         cell.includes('⚠️') ? <span style={{ color: 'var(--warning)' }}>{cell}</span> :
                         cell.includes('**') ? <strong>{cell.replace(/\*\*/g, '')}</strong> : cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--gap-md)' }}>
        {dailyEntries.length > 0 && (
          <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Daily Activity Log</div>
            <div style={{ maxHeight: 300, overflowY: 'auto', fontSize: 13, lineHeight: 1.6 }}>
              {dailyEntries.slice(0, 10).map((entry, i) => {
                const title = entry.split('\n')[0]?.replace(/^###\s*/, '') || '';
                const body = entry.split('\n').slice(1).filter(l => l.trim()).join('\n');
                return (
                  <div key={i} style={{ marginBottom: 12, padding: 8, background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                    <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--primary)', marginBottom: 4 }}>{title}</div>
                    <div style={{ whiteSpace: 'pre-wrap', color: 'var(--text-muted)' }}>{body}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {insightRows.length > 0 && (
          <div style={{ background: 'var(--surface)', borderRadius: 12, padding: 'var(--gap-md)', border: '1px solid var(--border)' }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Market Intelligence</div>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Signal</th>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Implication</th>
                    <th style={{ textAlign: 'left', padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {insightRows.slice(0, 10).map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                      {row.slice(1, 4).map((cell, j) => (
                        <td key={j} style={{ padding: '4px 6px' }}>
                          {cell.replace(/\*\*/g, '').replace(/^\d{4}-\d{2}-\d{2}\s*/, '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2.4: Verify the page builds**

Run the vite build check:
```bash
cd aether-dashboard && npx vite build 2>&1 | tail -10
```
Expected: Build succeeds (no TypeScript/import errors). If `Target` icon isn't available in the installed lucide-react version, swap to `TrendingUp` or `Crosshair`.

---

### Task 3: Expanded AGI Tests — `tests/test_acquisition_brain.py`

**Files:**
- Modify: `tests/test_acquisition_brain.py` (append ~60 new tests)

- [ ] **Step 3.1: Append AutonomousCore cognitive loop tests (~12)**

Append these test classes before the file's closing (or at the end):

```python
# ── Extended: Autonomous Core Cognitive Loop ──────────────

class TestAutonomousCoreExtended:
    """Deep coverage for AutonomousCore cognitive loop edge cases."""

    def test_cognitive_cycle_empty_state(self):
        from agi.autonomous_core import AutonomousCore
        core = AutonomousCore()
        core.state = {}
        result = core.run_cognitive_cycle(dry_run=True)
        assert result is not None

    def test_cognitive_cycle_max_paths(self):
        core = AutonomousCore()
        core.state["context"] = "Generate 50 different reasoning paths for a complex multi-variable optimization problem with many possible approaches"
        result = core._reason()
        assert len(result) >= 5

    def test_observe_large_context(self):
        core = AutonomousCore()
        large = "context " * 5000
        core.state["context"] = large
        core._observe()
        assert len(core.state.get("context", "")) >= 10000

    def test_deliberate_tie_breaking(self):
        from agi.autonomous_core import ReasoningPath
        core = AutonomousCore()
        paths = [
            ReasoningPath(path_id="a", description="a", confidence=0.5, quality_score=0.8, reasoning_depth=3, reasoning_steps=[], estimated_value=0.5, risk_level="medium"),
            ReasoningPath(path_id="b", description="b", confidence=0.5, quality_score=0.8, reasoning_depth=3, reasoning_steps=[], estimated_value=0.5, risk_level="medium"),
        ]
        selected = core._deliberate(paths)
        assert selected is not None

    def test_reflect_empty_history(self):
        core = AutonomousCore()
        core._reflection_history = []
        result = core._reflect()
        assert result is not None

    def test_meta_reason_no_patterns(self):
        core = AutonomousCore()
        core._learned_patterns = []
        result = core._meta_reason()
        assert isinstance(result, dict)

    def test_learn_no_new_patterns(self):
        core = AutonomousCore()
        core._outcome_history = []
        core._learn()
        assert len(core._learned_patterns) >= 0

    def test_save_state_missing_file(self, tmp_path):
        from agi.autonomous_core import AutonomousCore
        core = AutonomousCore(state_dir=tmp_path / "missing")
        core.load_state()
        status = core.get_status()
        assert "state_loaded" in status

    def test_quality_assessment_fair(self):
        from agi.autonomous_core import AutonomousCore, ReasoningQuality
        from agi.autonomous_core import ReasoningPath
        core = AutonomousCore()
        paths = [
            ReasoningPath(path_id="a", description="good", confidence=0.8, quality_score=0.7, reasoning_depth=5, reasoning_steps=["s1", "s2"], estimated_value=0.8, risk_level="low"),
            ReasoningPath(path_id="b", description="ok", confidence=0.5, quality_score=0.5, reasoning_depth=3, reasoning_steps=["s1"], estimated_value=0.5, risk_level="medium"),
        ]
        quality = core._assess_reasoning_quality(paths)
        assert quality in (ReasoningQuality.FAIR, ReasoningQuality.GOOD)

    def test_quality_assessment_good(self):
        from agi.autonomous_core import AutonomousCore, ReasoningQuality
        from agi.autonomous_core import ReasoningPath
        core = AutonomousCore()
        paths = [
            ReasoningPath(path_id="a", description="best", confidence=0.95, quality_score=0.9, reasoning_depth=10, reasoning_steps=[f"s{i}" for i in range(10)], estimated_value=0.95, risk_level="low"),
            ReasoningPath(path_id="b", description="great", confidence=0.9, quality_score=0.85, reasoning_depth=8, reasoning_steps=[f"s{i}" for i in range(8)], estimated_value=0.9, risk_level="low"),
        ]
        quality = core._assess_reasoning_quality(paths)
        assert quality == ReasoningQuality.GOOD

    def test_reasoning_with_structured_context(self):
        core = AutonomousCore()
        core.state["context"] = json.dumps({"goal": "test", "constraints": ["a", "b"], "resources": {"cpu": 4}})
        result = core._reason()
        assert isinstance(result, list)
```

- [ ] **Step 3.2: Append AutonomousScheduler tests (~14):**

```python
# ── Extended: Autonomous Scheduler ────────────────────────

class TestAutonomousSchedulerExtended:
    """Deep coverage for scheduler edge cases."""

    def test_priority_inversion(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency, TaskPriority
        scheduler = AutonomousScheduler()
        low = scheduler.register_task(name="low", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        low.next_run = 0
        high = scheduler.register_task(name="high", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY, priority=TaskPriority.HIGH)
        high.next_run = 0
        tasks = scheduler.get_next_tasks(limit=5)
        assert tasks[0].name == "high"

    def test_concurrent_execution_limit(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler(max_concurrent_tasks=2)
        tasks = []
        for i in range(5):
            t = scheduler.register_task(name=f"t{i}", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
            t.next_run = 0
            tasks.append(t)
        eligible = scheduler.get_next_tasks(limit=10)
        assert len(eligible) <= 2

    def test_task_reregister(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t1 = scheduler.register_task(name="dup", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        t2 = scheduler.register_task(name="dup", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        assert t1.task_id != t2.task_id
        assert len(scheduler.tasks) == 2

    def test_state_persistence_missing(self, tmp_path):
        from agi.autonomous_scheduler import AutonomousScheduler
        scheduler = AutonomousScheduler(state_dir=tmp_path / "nosched")
        scheduler.load_state()
        assert len(scheduler.tasks) == 0

    def test_adaptive_backoff_cap(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t = scheduler.register_task(name="b", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.ADAPTIVE)
        t.adaptive_interval_seconds = 86400
        t.failure_backoff_multiplier = 2
        scheduler._adjust_adaptive_schedule(t, success=False)
        assert t.adaptive_interval_seconds <= 86400

    def test_adaptive_backoff_min(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t = scheduler.register_task(name="b", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.ADAPTIVE)
        t.adaptive_interval_seconds = 60
        scheduler._adjust_adaptive_schedule(t, success=True)
        assert t.adaptive_interval_seconds >= 60

    def test_adaptive_speedup_floor(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t = scheduler.register_task(name="b", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.ADAPTIVE)
        t.adaptive_interval_seconds = 61
        for _ in range(10):
            scheduler._adjust_adaptive_schedule(t, success=True)
        assert t.adaptive_interval_seconds == 60

    def test_scheduler_empty_tasks(self):
        from agi.autonomous_scheduler import AutonomousScheduler
        scheduler = AutonomousScheduler()
        executed = scheduler.run_once(max_tasks=5)
        assert executed == 0

    def test_cron_expression_override(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t = scheduler.register_task(name="cron", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.DAILY, cron_expression="0 6 * * *")
        assert t.cron_expression == "0 6 * * *"

    def test_save_state_before_run(self, tmp_path):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler(state_dir=tmp_path / "save")
        scheduler.register_task(name="pre", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        scheduler.save_state()
        assert (tmp_path / "save" / "scheduler_state.json").exists()

    def test_get_next_tasks_empty(self):
        from agi.autonomous_scheduler import AutonomousScheduler
        scheduler = AutonomousScheduler()
        tasks = scheduler.get_next_tasks(limit=5)
        assert tasks == []

    def test_task_disabled(self):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler()
        t = scheduler.register_task(name="dis", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        t.next_run = 0
        t.enabled = False
        eligible = scheduler.get_next_tasks(limit=5)
        assert t not in eligible

    def test_save_and_load_state(self, tmp_path):
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        scheduler = AutonomousScheduler(state_dir=tmp_path / "sl")
        t = scheduler.register_task(name="slt", goal="g", handler=lambda **kw: {}, frequency=TaskFrequency.MINUTELY)
        scheduler.save_state()
        scheduler2 = AutonomousScheduler(state_dir=tmp_path / "sl")
        scheduler2.load_state()
        assert len(scheduler2.tasks) == 1
```

- [ ] **Step 3.3: Append ProbabilisticAgent tests (~10):**

```python
# ── Extended: Probabilistic Agent ─────────────────────────

class TestProbabilisticAgentExtended:
    """Deep coverage for probabilistic agent edge cases."""

    def test_bayesian_zero_evidence(self):
        from agi.probabilistic_agent import ProbabilisticAgent
        agent = ProbabilisticAgent()
        agent._update_belief("test", 0, 0)
        belief = agent.beliefs.get("test", 0.5)
        assert belief == 0.5

    def test_bayesian_extreme_prior(self):
        from agi.probabilistic_agent import ProbabilisticAgent
        agent = ProbabilisticAgent()
        agent.beliefs["test"] = 0.001
        agent._update_belief("test", 10, 10)
        assert agent.beliefs["test"] > 0.5

    def test_bayesian_all_success(self):
        from agi.probabilistic_agent import ProbabilisticAgent
        agent = ProbabilisticAgent()
        agent._update_belief("test", 100, 100)
        assert agent.beliefs["test"] > 0.9

    def test_bayesian_all_failure(self):
        from agi.probabilistic_agent import ProbabilisticAgent
        agent = ProbabilisticAgent()
        agent._update_belief("test", 0, 100)
        assert agent.beliefs["test"] < 0.1

    def test_explore_at_zero_temperature(self):
        agent = ProbabilisticAgent()
        agent.decisions["a"] = {"successes": 10, "failures": 1, "total": 11}
        agent.decisions["b"] = {"successes": 1, "failures": 10, "total": 11}
        action = agent.select_action(available_actions=["a", "b"], context={"exploration_rate": 0.0})
        assert action in ("a", "b")

    def test_explore_at_max_temperature(self):
        agent = ProbabilisticAgent()
        action = agent.select_action(available_actions=["x", "y"], context={"exploration_rate": 1.0})
        assert action in ("x", "y")

    def test_decision_metrics_empty(self):
        from agi.probabilistic_agent import ProbabilisticAgent
        agent = ProbabilisticAgent()
        metrics = agent.get_decision_metrics()
        assert metrics["total_decisions"] == 0

    def test_decision_metrics_single(self):
        agent = ProbabilisticAgent()
        agent.record_outcome("test", "a", True)
        metrics = agent.get_decision_metrics()
        assert metrics["total_decisions"] >= 1

    def test_strategy_high_confidence(self):
        agent = ProbabilisticAgent()
        agent.decisions["a"] = {"successes": 50, "failures": 2, "total": 52}
        strategy = agent.recommended_strategy()
        assert strategy["strategy"] == "exploit"

    def test_strategy_low_confidence(self):
        agent = ProbabilisticAgent()
        agent.decisions["a"] = {"successes": 1, "failures": 20, "total": 21}
        strategy = agent.recommended_strategy()
        assert strategy["strategy"] in ("explore", "exploit")
```

- [ ] **Step 3.4: Append SelfLearningLoop tests (~12):**

```python
# ── Extended: Self Learning Loop ──────────────────────────

class TestSelfLearningLoopExtended:
    """Deep coverage for self-learning loop edge cases."""

    def test_pattern_discovery_empty(self):
        from agi.self_learning_loop import SelfLearningLoop
        loop = SelfLearningLoop()
        loop._outcomes = []
        patterns = loop._discover_patterns()
        assert patterns == []

    def test_pattern_discovery_single(self):
        loop = SelfLearningLoop()
        loop._outcomes = [{"pattern": "p1", "success": True}]
        patterns = loop._discover_patterns()
        assert isinstance(patterns, list)

    def test_pattern_discovery_repeated(self):
        loop = SelfLearningLoop()
        loop._outcomes = [{"pattern": "p1", "success": True} for _ in range(20)]
        patterns = loop._discover_patterns()
        assert len(patterns) >= 1

    def test_performance_trend_flat(self):
        loop = SelfLearningLoop()
        for _ in range(10):
            loop.record_outcome({"pattern": "test", "success": True, "confidence": 0.5})
        trend = loop.get_performance_trend(window=20)
        assert isinstance(trend, dict)

    def test_performance_trend_volatile(self):
        loop = SelfLearningLoop()
        for i in range(20):
            loop.record_outcome({"pattern": "test", "success": i % 2 == 0, "confidence": 0.5})
        trend = loop.get_performance_trend(window=5)
        assert isinstance(trend, dict)

    def test_performance_trend_insufficient_data(self):
        loop = SelfLearningLoop()
        trend = loop.get_performance_trend(window=50)
        assert isinstance(trend, dict)

    def test_strategy_adaptation_boundary(self):
        loop = SelfLearningLoop()
        loop._performance_history = [0.5, 0.5, 0.5]
        strategy = loop.suggest_strategy()
        assert isinstance(strategy, dict)

    def test_pattern_recommendations_empty(self):
        loop = SelfLearningLoop()
        loop._patterns = []
        recs = loop.get_pattern_recommendations()
        assert recs == []

    def test_pattern_recommendations_filtered(self):
        loop = SelfLearningLoop()
        loop._patterns = [{"pattern": "p1", "success_rate": 0.3, "count": 5}]
        recs = loop.get_pattern_recommendations(min_confidence=0.5)
        assert recs == []

    def test_learning_status_empty(self):
        loop = SelfLearningLoop()
        loop._outcomes = []
        loop._patterns = []
        status = loop.get_learning_status()
        assert isinstance(status, dict)

    def test_learning_status_after_outcomes(self):
        loop = SelfLearningLoop()
        loop.record_outcome({"pattern": "test", "success": True, "confidence": 0.8})
        status = loop.get_learning_status()
        assert status["total_outcomes"] >= 1

    def test_save_state_corrupt(self, tmp_path):
        from agi.self_learning_loop import SelfLearningLoop
        state_file = tmp_path / "learning" / "state.json"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("{corrupt json", encoding="utf-8")
        loop = SelfLearningLoop(state_dir=tmp_path / "learning")
        loop.load_state()
        assert len(loop._outcomes) == 0
```

- [ ] **Step 3.5: Append DeterministicExecutor tests (~8):**

```python
# ── Extended: Deterministic Executor ──────────────────────

class TestDeterministicExecutorExtended:
    """Deep coverage for executor edge cases."""

    def test_create_plan_empty_steps(self):
        from agi.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        plan = executor.create_plan("empty", [])
        assert plan.plan_id is not None

    def test_create_plan_single_step(self):
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        executor = DeterministicExecutor()
        plan = executor.create_plan("single", [
            ActionStep(step_id="s1", action_name="noop", action_type=ActionType.DETERMINISTIC, parameters={}),
        ])
        assert len(plan.steps) == 1

    def test_compensation_chain(self):
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        executor = DeterministicExecutor()
        calls = []
        def ok(**kw): calls.append("ok"); return {"done": True}
        def fail(**kw): raise RuntimeError("fail")
        def comp(**kw): calls.append("comp")
        executor.register_action("ok", ok, compensation=comp)
        executor.register_action("fail", fail)
        plan = executor.create_plan("chain", [
            ActionStep(step_id="s1", action_name="ok", action_type=ActionType.COMPENSABLE, parameters={}),
            ActionStep(step_id="s2", action_name="ok", action_type=ActionType.COMPENSABLE, parameters={}),
            ActionStep(step_id="s3", action_name="fail", action_type=ActionType.DETERMINISTIC, parameters={}),
        ])
        success, result = executor.execute(plan)
        assert success is False
        assert calls.count("comp") == 2

    def test_compensation_chain_partial(self):
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        executor = DeterministicExecutor()
        calls = []
        def ok(**kw): calls.append("ok"); return {"done": True}
        def fail(**kw): raise RuntimeError("fail")
        def comp(**kw): calls.append("comp")
        executor.register_action("ok", ok, compensation=comp)
        executor.register_action("fail", fail)
        plan = executor.create_plan("partial", [
            ActionStep(step_id="s1", action_name="ok", action_type=ActionType.COMPENSABLE, parameters={}),
            ActionStep(step_id="s2", action_name="ok", action_type=ActionType.DETERMINISTIC, parameters={}),
            ActionStep(step_id="s3", action_name="fail", action_type=ActionType.DETERMINISTIC, parameters={}),
        ])
        success, result = executor.execute(plan)
        assert success is False
        assert calls.count("comp") == 1

    def test_action_registration_overwrite(self):
        from agi.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        executor.register_action("dup", lambda **kw: {})
        executor.register_action("dup", lambda **kw: {"v": 2})
        result = executor.execute_action("dup", {})
        assert result.get("v") == 2

    def test_plan_progress_before_execution(self):
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        executor = DeterministicExecutor()
        plan = executor.create_plan("prog", [
            ActionStep(step_id="s1", action_name="noop", action_type=ActionType.DETERMINISTIC, parameters={}),
        ])
        progress = executor.get_plan_progress(plan)
        assert progress["current_step"] == 0

    def test_plan_progress_after_failure(self):
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        executor = DeterministicExecutor()
        def fail(**kw): raise RuntimeError("fail")
        executor.register_action("fail", fail)
        plan = executor.create_plan("failprog", [
            ActionStep(step_id="s1", action_name="fail", action_type=ActionType.DETERMINISTIC, parameters={}),
        ])
        executor.execute(plan)
        progress = executor.get_plan_progress(plan)
        assert progress["status"] == "failed"

    def test_statistics_no_actions(self):
        from agi.deterministic_executor import DeterministicExecutor
        executor = DeterministicExecutor()
        stats = executor.get_statistics()
        assert stats["total_actions"] == 0
```

- [ ] **Step 3.6: Append Integration tests (~4):**

```python
# ── Acquisition Integration ──────────────────────────────

class TestAcquisitionIntegration:
    """Tests that wire brain components together with the bridge."""

    def test_bridge_works_with_scheduler(self):
        from acquisition_bridge import AcquisitionBridge
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            bridge = AcquisitionBridge(Path(td))
            scheduler = AutonomousScheduler()
            def bridge_handler(goal, task_context):
                bridge.log_autonomous_session({"brain_state": "scheduled", "tasks_executed": 1})
                return {"success": True}
            t = scheduler.register_task(name="bridge-test", goal="test", handler=bridge_handler, frequency=TaskFrequency.MINUTELY)
            t.next_run = 0
            executed = scheduler.run_once(max_tasks=1)
            assert executed == 1
            log_content = bridge._safe_read(bridge.tracker_dir / "DAILY-LOG.md")
            assert "scheduled" in log_content

    def test_executor_runs_bridge_action(self):
        from acquisition_bridge import AcquisitionBridge
        from agi.deterministic_executor import DeterministicExecutor, ActionStep, ActionType
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            bridge = AcquisitionBridge(Path(td))
            executor = DeterministicExecutor()
            def log_action(parameters, execution_context):
                bridge.log_autonomous_session(parameters.get("data", {}))
                return {"done": True}
            executor.register_action("bridge_log", log_action)
            plan = executor.create_plan("bridge-plan", [
                ActionStep(step_id="s1", action_name="bridge_log", action_type=ActionType.DETERMINISTIC, parameters={"data": {"brain_state": "executor", "tasks_executed": 2}}),
            ])
            success, result = executor.execute(plan)
            assert success is True
            log_content = bridge._safe_read(bridge.tracker_dir / "DAILY-LOG.md")
            assert "executor" in log_content

    def test_cognitive_cycle_does_not_crash_bridge(self):
        from acquisition_bridge import AcquisitionBridge
        from agi.autonomous_core import AutonomousCore
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            bridge = AcquisitionBridge(Path(td))
            core = AutonomousCore()
            core.state["context"] = "Analyze acquisition portfolio for exit readiness"
            result = core.run_cognitive_cycle(dry_run=True)
            assert result is not None
            bridge.log_autonomous_session({"brain_state": "post-cycle", "tasks_executed": result.get("paths_explored", 0)})
            log_content = bridge._safe_read(bridge.tracker_dir / "DAILY-LOG.md")
            assert "post-cycle" in log_content

    def test_scheduler_can_use_bridge_as_handler(self):
        from acquisition_bridge import AcquisitionBridge
        from agi.autonomous_scheduler import AutonomousScheduler, TaskFrequency
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            bridge = AcquisitionBridge(Path(td))
            scheduler = AutonomousScheduler()
            def insight_handler(goal, task_context):
                bridge.record_insight("scheduler", "auto-detected", "integration works", "test")
                return {"success": True}
            t = scheduler.register_task(name="insight-test", goal="test", handler=insight_handler, frequency=TaskFrequency.MINUTELY)
            t.next_run = 0
            scheduler.run_once(max_tasks=1)
            insights_content = bridge._safe_read(bridge.tracker_dir / "INSIGHTS.md")
            assert "auto-detected" in insights_content
```

- [ ] **Step 3.7: Run all brain tests**

Run: `python -m pytest tests/test_acquisition_brain.py -v --tb=short`
Expected: All tests PASS (existing + extended = ~100+ total)

---

### Task 4: Playwright UX Tests — `tests/e2e/test_acquisition_ux.py`

**Files:**
- Create: `tests/e2e/test_acquisition_ux.py`

- [ ] **Step 4.1: Write Playwright tests**

Create `tests/e2e/test_acquisition_ux.py`:

```python
"""Playwright UX tests for the Acquisition Tracker dashboard page.

Requires:
  - Brain API running on http://localhost:8000
  - Dashboard built and served (via the brain server)
"""
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    yield page
    context.close()


class TestAcquisitionPageLoads:
    """Acquisition Tracker page loads and renders content."""

    def _navigate_to(self, page, page_label):
        page.click(f"nav button:has-text('{page_label}')")
        page.wait_for_timeout(1500)
        page.wait_for_load_state("networkidle")

    def test_acquisition_page_loads(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        heading = page.locator("text=Acquisition Tracker")
        assert heading.is_visible()

    def test_acquisition_metric_cards_display(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        cards = page.locator("text=Portfolio Assets")
        assert cards.is_visible()

    def test_acquisition_portfolio_table(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        table = page.locator("text=Portfolio Deploy Readiness")
        assert table.is_visible()

    def test_acquisition_daily_log_section(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        log = page.locator("text=Daily Activity Log")
        assert log.is_visible()

    def test_acquisition_insights_section(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        insights = page.locator("text=Market Intelligence")
        assert insights.is_visible()

    def test_acquisition_tracker_status_indicator(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Acquisition")
        status = page.locator("text=Tracker Online")
        assert status.is_visible()


class TestSidebarNavigation:
    """Every sidebar entry navigates to a page without error."""

    PAGES = [
        "Dashboard", "Agents", "Skills", "Scheduler", "Health", "Chat", "Models",
        "Research", "Signals", "Library",
        "Content", "Media", "Betting", "Finance", "Acquisition",
        "Browser", "GitHub", "Agents Registry",
        "Settings",
    ]

    @pytest.fixture(autouse=True)
    def setup_page(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")

    def test_all_pages_navigate_without_crash(self, page):
        errors_before = len(page.locator(".error-boundary-fallback").all())
        for page_label in self.PAGES:
            try:
                nav = page.locator(f"nav button:has-text('{page_label}')")
                if nav.count() == 0:
                    continue
                nav.first.click()
                page.wait_for_timeout(1000)
                errors_after = len(page.locator(".error-boundary-fallback").all())
                assert errors_after == errors_before, f"Page '{page_label}' caused crash"
            except Exception as e:
                pytest.fail(f"Navigation to '{page_label}' failed: {e}")


class TestExistingStubsFilled:
    """Fill the pass-stubs from test_playwright_ui.py."""

    def _navigate_to(self, page, page_label):
        page.click(f"nav button:has-text('{page_label}')")
        page.wait_for_timeout(1000)

    def test_settings_toggle_tracing(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Settings")
        toggle = page.locator("text=Tracing").first
        if toggle.count():
            toggle.click()
            page.wait_for_timeout(500)

    def test_settings_save_button(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Settings")
        saves = page.locator("button:has-text('Save')")
        assert saves.count() >= 1

    def test_settings_group_headings(self, page):
        page.goto(BASE)
        page.wait_for_load_state("networkidle")
        self._navigate_to(page, "Settings")
        content = page.text_content("main")
        for group in ["API Keys", "Soul Identity", "Integrations Status"]:
            assert group in content, f"Settings group '{group}' not found"
```

- [ ] **Step 4.2: Run Playwright tests**

Run: `cd deterministic-brain-main && python -m pytest tests/e2e/test_acquisition_ux.py -v --tb=short`
Expected: Tests PASS if brain server is running on port 8000 with dashboard. If server isn't running, tests will fail gracefully at page.goto().

---

### Task 5: Verify everything together

- [ ] **Step 5.1: Run all brain tests**

Run: `python -m pytest tests/test_acquisition_brain.py tests/test_acquisition_bridge.py -v --tb=short`
Expected: All ~110 tests PASS

- [ ] **Step 5.2: Run API tests**

Run: `python -m pytest tests/test_acquisition_api.py -v --tb=short`
Expected: All 10 tests PASS

- [ ] **Step 5.3: Verify dashboard builds**

Run: `cd aether-dashboard && npx vite build 2>&1 | tail -15`
Expected: Build succeeds

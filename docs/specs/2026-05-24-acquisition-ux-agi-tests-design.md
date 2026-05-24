# Acquisition Tracker UX + Expanded AGI Testing

## Goal
Add an Acquisition Tracker page to the aether-dashboard (React), expose bridge data via brain API endpoints, expand AGI component test coverage to ~60 new tests, and add ~15 Playwright UX tests.

## API Layer — `api/routes/acquisition.py`

### Endpoints
| Endpoint | Method | Bridge Method | Returns |
|---|---|---|---|
| `/api/acquisition/status` | GET | `bridge.get_status()` | `{tracker_dir, files_present, last_sync}` |
| `/api/acquisition/daily-log` | GET | reads DAILY-LOG.md | `{content: string}` |
| `/api/acquisition/daily-log` | POST | `bridge.log_autonomous_session()` | `{status: "ok"}` |
| `/api/acquisition/progress` | GET | reads PROGRESS.md | `{content: string}` |
| `/api/acquisition/progress` | POST | `bridge.update_portfolio_progress()` | `{status: "ok"}` |
| `/api/acquisition/insights` | GET | reads INSIGHTS.md | `{content: string}` |
| `/api/acquisition/insights` | POST | `bridge.record_insight()` | `{status: "ok"}` |
| `/api/acquisition/metrics` | GET | reads METRICS.md | `{content: string}` |
| `/api/acquisition/metrics` | POST | `bridge.refresh_metrics()` | `{status: "ok"}` |

### Router pattern
- Single `APIRouter(prefix="/api/acquisition", tags=["acquisition"])`
- Singleton bridge: `_bridge = None`, lazy init with `AcquisitionBridge()`
- All GET endpoints use `_safe_read()` for resilience
- Registered in `api/server.py` via `app.include_router(acquisition_router)`

## UI Page — `aether-dashboard/src/pages/AcquisitionTracker.jsx`

### Layout
```
┌──────────────────────────────────────────────────────────────┐
│ 🎯 Acquisition Tracker                                       │
│ Live portfolio health, daily ops, market intel                │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────┐ │
│ │ Portfolio    │ │ Daily        │ │ Insights     │ │Score │ │
│ │ Status       │ │ Activity     │ │ Count        │ │ 83%  │ │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────┘ │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐ │
│ │  Portfolio Deploy Readiness Table                        │ │
│ │  Asset │ Deploy │ B │ T │ E │ D │ Updated               │ │
│ │  Uplift│ 95%    │ ✅│ ✅│ ✅│ ✅│ 05-24                  │ │
│ │  UL2   │ 90%    │ ✅│ ✅│ ✅│ ✅│ 05-24                  │ │
│ │  ...   │ ...    │   │   │   │   │                        │ │
│ └──────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌────────────────────────────────────┐ │
│ │ Daily Log        │  │ Market Insights                    │ │
│ │ ─────────        │  │ ──────────────────                 │ │
│ │ 05-24 — Auto Ses │  │ Signal │ Implication │ Action      │ │
│ │ 05-24 — Sess 1   │  │ ...    │ ...         │ ...         │ │
│ └──────────────────┘  └────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│ Metrics + radar chart (recharts)                             │
└──────────────────────────────────────────────────────────────┘
```

### Key details
- Uses existing `MetricCard`, `useAutoRefresh`, API pattern from `BrainOps.jsx`
- New API functions in `src/api.js`: `getAcquisitionStatus`, `getAcquisitionLog`, `postAcquisitionLog`, etc.
- Sidebar entry inserted between "Intel Hub" and "Media Studio"
- Icon: `Target` from lucide-react (or `BarChart3`)
- Auto-refresh every 10s
- Markdown content rendered with simple text display (not full MD renderer)

## Expanded AGI Tests — `tests/test_acquisition_brain.py`

### AutonomousCore (~12 new)
- `test_cognitive_cycle_empty_state` — cycle with no prior state
- `test_cognitive_cycle_max_paths` — force 50+ reasoning paths
- `test_observe_large_context` — 10K+ char observation
- `test_reason_exhaustive` — explore all paths (quality ceiling)
- `test_deliberate_tie_breaking` — equal scores resolve deterministically
- `test_reflect_empty_history` — no prior reflections
- `test_meta_reason_no_patterns` — no patterns to meta-reason about
- `test_learn_no_new_patterns` — no new knowledge from cycle
- `test_save_state_corrupt_file` — load corrupted state file
- `test_save_state_missing_file` — load non-existent state
- `test_quality_assessment_fair` — mixed reasoning quality
- `test_quality_assessment_good` — high quality reasoning

### AutonomousScheduler (~14 new)
- `test_priority_inversion` — high-priority task added after low-priority ones
- `test_concurrent_execution_limit` — more tasks than max_concurrent
- `test_task_disable_during_execution` — disable while running
- `test_task_reregister` — register same task twice
- `test_state_persistence_corrupt` — load corrupted state
- `test_state_persistence_missing` — load non-existent state
- `test_adaptive_backoff_cap` — backoff at max interval boundary
- `test_adaptive_backoff_min` — interval at min boundary
- `test_adaptive_speedup_floor` — speed up reaches min interval
- `test_task_execution_timeout` — handler that never returns
- `test_scheduler_empty_tasks` — run_once with zero tasks
- `test_cron_expression_override` — frequency vs cron_expression interaction
- `test_save_state_before_run` — persist before any execution
- `test_get_next_tasks_empty` — no eligible tasks

### ProbabilisticAgent (~10 new)
- `test_bayesian_zero_evidence` — update with 0 successes, 0 trials
- `test_bayesian_extreme_prior` — prior at 0.001 and 0.999
- `test_bayesian_all_success` — 100% success rate
- `test_bayesian_all_failure` — 0% success rate
- `test_explore_at_zero_temperature` — exploration=0, must still return something
- `test_explore_at_max_temperature` — max randomness
- `test_decision_metrics_empty` — no decisions recorded
- `test_decision_metrics_single` — single decision
- `test_strategy_high_confidence` — high confidence strategy recommendation
- `test_strategy_low_confidence` — low confidence recommendation

### SelfLearningLoop (~12 new)
- `test_pattern_discovery_empty` — no outcomes to discover patterns from
- `test_pattern_discovery_single` — single outcome
- `test_pattern_discovery_repeated` — same pattern repeated
- `test_performance_trend_flat` — no change over time
- `test_performance_trend_volatile` — fluctuating performance
- `test_performance_trend_insufficient_data` — less than min data points
- `test_strategy_adaptation_boundary` — confidence at 0.5 boundary
- `test_pattern_recommendations_empty` — no patterns
- `test_pattern_recommendations_filtered` — patterns below threshold
- `test_learning_status_empty` — no learning data
- `test_learning_status_after_outcomes` — after recording outcomes
- `test_save_state_corrupt` — load corrupted state file

### DeterministicExecutor (~8 new)
- `test_create_plan_empty_steps` — plan with zero steps
- `test_create_plan_single_step` — single step plan
- `test_compensation_chain` — multiple compensable steps, rollback all
- `test_compensation_chain_partial` — mix of compensable and non-compensable
- `test_action_registration_overwrite` — register same action name twice
- `test_plan_progress_before_execution` — progress at init state
- `test_plan_progress_after_failure` — progress after failed step
- `test_statistics_no_actions` — no actions registered

### AcquisitionBridge (~4 new)
- `test_concurrent_write_read` — write and read simultaneously across threads
- `test_state_across_instances_different_dirs` — isolation between dirs
- `test_large_unicode_log` — very long unicode strings in log
- `test_bridge_init_custom_dir` — custom tracker dir path

### Integration (~4 new)
- `test_scheduler_bridge_full_cycle` — scheduler triggers bridge action, cognitive cycle executes
- `test_executor_acquisition_plan` — executor runs acquisition action chain
- `test_brain_logs_after_cognitive_cycle` — after cognitive cycle, DAILY-LOG.md updated
- `test_scheduler_persists_and_recovers` — scheduler persists state, restarts, continues

## Playwright UX Tests — `tests/e2e/test_acquisition_ux.py`

New test file with Playwright tests:

### Tests (~15)
1. `test_acquisition_page_loads` — Navigate to acquisition page, observe heading
2. `test_acquisition_metric_cards_display` — 4 metric cards render with values
3. `test_acquisition_portfolio_table` — Portfolio table rows render
4. `test_acquisition_daily_log_section` — Daily log section visible with entries
5. `test_acquisition_insights_section` — Insights section visible
6. `test_acquisition_metrics_section` — Metrics/score section visible
7. `test_acquisition_auto_refresh` — Data refreshes on interval
8. `test_acquisition_post_updates_page` — POST through API, verify page reflects
9. `test_sidebar_navigation_all_pages` — Every sidebar entry navigates without crash
10. `test_devpets_page_loads` — Fill existing Pass stub
11. `test_battle_page_loads` — Fill existing Pass stub
12. `test_health_page_loads` — Fill existing Pass stub
13. `test_settings_toggle_tracing` — Fill existing stub
14. `test_routing_page_route_test` — Fill existing RouteTest stub
15. `test_scheduler_page_loads` — Fill existing stub

## Files to Create/Modify

### New files
- `api/routes/acquisition.py` — FastAPI router
- `aether-dashboard/src/pages/AcquisitionTracker.jsx` — React page
- `tests/e2e/test_acquisition_ux.py` — Playwright tests

### Modified files
- `api/server.py` — Import + register acquisition router, add sidebar entry for dashboard
- `aether-dashboard/src/api.js` — Add acquisition API functions
- `aether-dashboard/src/App.jsx` — Add route + sidebar entry
- `tests/test_acquisition_brain.py` — Add ~60 new tests

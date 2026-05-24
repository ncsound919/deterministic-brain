# Deterministic Brain — Chain Execution, Learning Loop & Qdrant Setup
**Date:** 2026-05-10
**Author:** Claude (via brainstorming)
**Status:** Draft

---

## 1. Problem Statement

The 2-hour benchmark revealed 4 critical gaps:

1. **Chain execution: 0% success** — `_execute_skill()` calls DCA with plain skill names, which hits a semantic MoE router that always returns low-confidence in deterministic mode. All 8 chains report "partial" with 0/3 steps OK.
2. **Contextual Bandit: 0 arms** — No skill outcomes are fed to `ContextualBandit`. The feedback loop exists in code (`reward_tracker.feed_bandit()`) but never fires because no arm registration happens on skill execution.
3. **AutoDream corrections: 0** — Correction detection pipeline is inactive in deterministic mode. No corrections = no learning correction signals.
4. **Qdrant vector dedup: always fails** — No Qdrant server running. Needs cloud cluster via browser automation.

---

## 2. Design

### 2.1 Gemma 3n E4B Local Inference Engine

**Goal:** Replace OpenRouter calls at critical deterministic-mode failure points with a local GGUF inference engine.

**Architecture:**
- Download `gemma-3n-E4B-it-Q4_K_M.gguf` (~4.2GB) to `models/gemma-3n-e4b-it-q4_k_m.gguf`
- Build llama.cpp from source on Windows (CMake + MinGW)
- Run as local API server on `localhost:8080`
- Expose via `tools/local_gemma.py` — thin client wrapping HTTP calls

**Fallback chain:**
1. Try deterministic keyword match (existing code)
2. If low confidence or no match → call local Gemma at `localhost:8080`
3. If Gemma unavailable → return low-confidence status (graceful degradation)

**Trigger points in codebase:**
- `skill_chains_loader._execute_skill()` — route skill name to correct skill path
- `brain/router.py` (MoERouter) — when deterministic score < threshold, call Gemma instead
- `orchestration/skill_executor.py` — when skill resolution fails, call Gemma for better matching
- `brain/autodream.py` — semantic analysis of traces, correction detection

**Runtime:**
- CPU inference (no GPU needed — E4B runs on consumer CPU)
- Typical latency: 5-15 tokens/sec on modern CPU
- Model loaded once, kept warm
- Port: 8080 (configurable via `.env` → `GEMMA_BASE_URL=http://localhost:8080`)

---

### 2.2 Chain Execution Fix

**Problem:** `_execute_skill()` passes skill name to `DCA.handle()` → semantic router → low confidence.

**Solution:** Direct skill registry lookup with Gemma-fallback.

**Flow:**
```
1. Check skill_chains.yaml for step.skill name
2. Look up in SkillRegistry: keyword match → skill path
3. If found: call SkillExecutor directly with inputs
4. If not found: call local Gemma to resolve skill name → path
5. Execute step
6. Record outcome → reward_tracker
7. Return status based on execution result
```

**New module: `tools/skill_resolver.py`**
- `resolve_skill(skill_name: str, inputs: Dict) -> Dict` — direct resolution with Gemma fallback
- `execute_skill_step(skill_name: str, inputs: Dict, chain: str, step: int) -> Dict` — full step execution with logging
- Integrates with `reward_tracker` to record outcomes for bandit feedback

**Chain success criteria (per option 1):**
- `status = "ok"` if all step results have `status != "error"` (partial/low-confidence OK)
- Post-steps run if `status != "error"`
- No crashes, no exceptions = success

---

### 2.3 Bandit Feedback Loop

**Problem:** No arms registered, no rewards observed.

**Root cause:** `SkillResolver` doesn't call `reward_tracker` after execution.

**Solution:**

**`tools/skill_resolver.py` (new) → `reward_tracker.record(arm_id, reward)`:**
```
After each skill step:
  arm_id = f"chain:{chain_name}:step:{step_index}:{skill_name}"
  reward = 0.5 if status == "ok" else 0.0
  reward_tracker.record(arm_id, reward)
```

**Auto-feed to bandit:**
- `reward_tracker.feed_bandit(bandit)` already exists — called on autodream_run event
- Bandit auto-creates arms from observed arm_ids
- Arm auto-created on first observation, updated on subsequent observations

**Gap:** Bandit uses channel/action/params format for marketing arms. Need to adapt for skill arms.

**New arm format:**
```python
arm_id = f"skill:{skill_name}"  # e.g., "skill:audit-repo"
channel = "chain_execution"
action = chain_category  # e.g., "marketing", "system"
params = {"chain": chain_name, "step": step_index}
```

---

### 2.4 AutoDream Correction Pipeline

**Problem:** `autodream_run` fires but corrections never appear.

**Root cause:** Correction detection reads `.autodream_corrections.jsonl` but no correction writer exists.

**Solution:**

**New module: `brain/correction_detector.py`**
```python
def detect_corrections() -> List[Dict]:
    # 1. Compare current trace outcomes vs. golden/reference traces
    # 2. Detect pattern: same skill + same inputs + different outputs
    # 3. Categorize: regression | drift | config_error | env_change
    # 4. Write to .autodream_corrections.jsonl
    # 5. Publish "correction_found" event
```

**Triggered by:** `autodream_run` event (already subscribed in `reward_tracker.py`)

**Correction types:**
- `regression`: skill that used to work now fails
- `drift`: outputs shifting over time without failure
- `config_error`: config change causing unexpected behavior
- `env_change`: new dependencies, API changes, path changes

**Integration with Healer:**
- `runtime_healer.py` already reads `.autodream_corrections.jsonl`
- Corrections auto-trigger healing actions

---

### 2.5 Qdrant Cloud Setup via Playwright

**Goal:** Create Qdrant Cloud free cluster, get API key, store in `.env`.

**Automation flow:**
1. Open `cloud.qdrant.io` in Playwright
2. Sign up with `tap4500@gmail.com`
3. Email verification — user provides code
4. Create free cluster (1GB RAM, us-east-1 region)
5. Extract API key from cluster settings
6. Write to `.env`:
   ```
   QDRANT_URL=https://<cluster-id>.cloud.qdrant.io
   QDRANT_API_KEY=<key>
   QDRANT_COLLECTION=brain_vectors
   ```
7. Test connection: create collection, insert test point, search

**Script: `scripts/setup_qdrant.py`**
- Uses Playwright with Chromium (headless=False — needs browser for auth)
- Wait for email verification code via user input
- Saves cluster URL + API key to `.env`
- Runs smoke test

**Graceful fallback:**
- If playwright setup fails, user can manually create cluster
- System detects `QDRANT_API_KEY` in `.env` and skips automated setup
- Qdrant errors in autodream already gracefully degrade (logged as "error", continues)

---

### 2.6 Neo4j Aura Integration

**Add to `.env`:**
```env
NEO4J_URI=neo4j+s://d8fe2bfe.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=<from credentials provided>
NEO4J_DATABASE=neo4j
```

**In `brain/autodream.py`:**
- Pass credentials from env → `GraphDatabase.driver()` → neo4j connector
- Enable Neo4j prune step (was previously skipped due to no driver)

---

## 3. File Changes

| File | Change |
|------|--------|
| `tools/local_gemma.py` | **NEW** — Gemma GGUF client, llama-server wrapper, inference API |
| `tools/skill_resolver.py` | **NEW** — Skill resolution with Gemma fallback, chain step execution, reward recording |
| `brain/correction_detector.py` | **NEW** — Correction detection from trace comparison |
| `features/skill_chains_loader.py` | **MOD** — Use SkillResolver instead of DCA handle() for step execution |
| `brain/autodream.py` | **MOD** — Enable Neo4j driver, enable correction detection, update Qdrant collection |
| `orchestration/runtime_healer.py` | **MOD** — Auto-trigger from correction events |
| `evolution/reward_tracker.py` | **MOD** — Ensure feed_bandit called on every skill execution outcome |
| `scripts/setup_qdrant.py` | **NEW** — Playwright automation for Qdrant Cloud signup |
| `.env` | **MOD** — Add NEO4J credentials, GEMMA_BASE_URL, QDRANT vars |
| `config.py` | **MOD** — Add Gemma config (base_url, model_path, threshold) |

---

## 4. Dependency Order

```
1. Setup Gemma (download model, build llama.cpp, start server)
2. Implement tools/local_gemma.py + test it
3. Implement tools/skill_resolver.py
4. Update skill_chains_loader.py to use SkillResolver
5. Update reward_tracker to record skill outcomes
6. Implement brain/correction_detector.py
7. Update autodream to use correction detector
8. Setup Qdrant via Playwright (user provides email code)
9. Update .env with Qdrant + Neo4j credentials
10. Run benchmark to verify chains now succeed
```

---

## 5. Success Criteria

- Chain execution: ≥50% chains return `status != "error"` (allow partial/low-confidence)
- Bandit: ≥5 arms registered within 10 cycles
- AutoDream corrections: ≥1 correction detected within 10 cycles
- Qdrant: vector search returns results (not "error")
- Neo4j: prune step executes (not "skipped")
- All 47 unit tests still pass
- No new crashes or exceptions in long_run benchmark
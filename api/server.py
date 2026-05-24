"""FastAPI server v2.5 — /task /reason /bundle /skills /forge /dashboard /relay /health"""
from __future__ import annotations
import json
import os
import re
import time
from datetime import datetime
import traceback
import asyncio
from functools import wraps
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import httpx

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from orchestration.event_bus import event_bus
from orchestration.skill_registry import get_skill_registry as _get_skill_registry
from brain.autodream import run_autodream, consolidate_knowledge_bank
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay
from api.middleware import RequestLoggingMiddleware, get_route_stats
from tools.metrics import get_metrics
import logging as _api_log
_api_logger = _api_log.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")

# ── Hermes Integration ─────────────────────────────────────────
HERMES_URL = os.getenv("HERMES_URL", "http://127.0.0.1:9119")
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:8082")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma-4-e2b.gguf")
_API_PORT = int(os.environ.get("API_PORT", 8000))

# Bundle config cache (avoid YAML parse on every /bundles request)
_BUNDLES_CACHE = {"mtime": 0, "bundles": []}

def _get_bundles_cached():
    import yaml
    config_path = os.environ.get("SWARM_CONFIG", "swarm.yaml")
    try:
        mtime = os.path.getmtime(config_path)
    except (OSError, IOError):
        mtime = 0
    if mtime != _BUNDLES_CACHE["mtime"]:
        try:
            with open(config_path, encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except Exception:
            config = {}
        bundles = []
        for name, data in config.get("bundles", {}).items():
            try:
                bd = BundleDefinition(**data)
                bundles.append({"name": name, "description": bd.description, "lanes": bd.lanes})
            except Exception as _be:
                import logging as _blog
                _blog.getLogger(__name__).warning("Skipping malformed bundle '%s': %s", name, _be)
        _BUNDLES_CACHE["mtime"] = mtime
        _BUNDLES_CACHE["bundles"] = bundles
    return {"bundles": _BUNDLES_CACHE["bundles"]}

# Precompiled security patterns for upload validation
_DANGEROUS_PATTERNS = [
    re.compile(r'\bos\.system\b', re.IGNORECASE),
    re.compile(r'\bsubprocess\b', re.IGNORECASE),
    re.compile(r'\beval\b', re.IGNORECASE),
    re.compile(r'\bexec\b', re.IGNORECASE),
    re.compile(r'\bcompile\b', re.IGNORECASE),
    re.compile(r'\b__import__\b', re.IGNORECASE),
    re.compile(r'ctypes', re.IGNORECASE),
    re.compile(r'socket\.', re.IGNORECASE),
    re.compile(r'\brm\s+-rf\b', re.IGNORECASE),
    re.compile(r'\bdangerous\b', re.IGNORECASE),
    re.compile(r'\bshutil\.rmtree\b', re.IGNORECASE),
]

# Promoted handler imports (remove lazy-import overhead from ~70 endpoints)
from brain.soul import get_soul
from features.finance_modules import get_news, get_odds, get_trading
from features.skill_chains_loader import get_chain_status, execute_chain
from features.betting_engine import get_bet_sheet
from features.betting_enhanced import (
    CircadianAnalyzer, FormulaEngine, get_enhanced_betting,
    SportsDataFeed, TrendAnalyzer,
)
from features.saas_builder import get_saas_builder
from features.social_scheduler import get_social
from features.chat_router import handle_chat
from features.planner import get_planner
from features.github_manager import get_github
from features.autonomy import get_autonomy
from features.scheduler import get_scheduler
from features.systems_bridge import get_systems_bridge
from features.template_builder import get_template_builder
from features.blackmind_lab import get_blackmind_lab
from features.agent_registry import get_agent_registry
from features.skill_expander import get_expander
from features.opportunity_scout import get_scout
from features.status_tracker import get_status_tracker
from features.prizepicks_scraper import get_prizepicks_scraper

# Route modules
from api.routes.settings import router as settings_router
from api.routes.voice import router as voice_router
from api.routes.devpets import router as devpets_router
from api.routes.kairos import router as kairos_router
from api.routes.evolution import router as evolution_router
from api.routes.social import router as social_router
from api.routes.media import router as media_router
from api.routes.knowledge import router as knowledge_router
from api.routes.agi import router as agi_router
from api.routes.acquisition import router as acquisition_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize SQLite databases on startup — WAL mode and schema."""
    _init_sqlite_wal()
    # Check distributed backends on startup
    if os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes"):
        try:
            from tools.postgres import get_pg_pool
            if get_pg_pool().available:
                _api_logger.info("PostgreSQL backend: available")
            else:
                _api_logger.warning("PostgreSQL backend: unavailable — using SQLite fallback")
        except Exception as e:
            _api_logger.warning("PostgreSQL backend: error — %s", e)
        try:
            from tools.redis_client import get_redis
            if get_redis().available:
                _api_logger.info("Redis backend: available")
            else:
                _api_logger.warning("Redis backend: unavailable — using in-memory fallback")
        except Exception as e:
            _api_logger.warning("Redis backend: error — %s", e)
    yield
    _close_sqlite_connections()


def _init_sqlite_wal():
    """Set WAL mode on all known SQLite databases at startup."""
    dbs = [
        os.environ.get("TRACE_DB", "traces.db"),
        "sovereign.db",
        "knowledge_bank/fragments.db",
    ]
    from pathlib import Path
    coo_db = Path(os.environ.get("COO_DATA_DIR", "data")) / "coo_state.db"
    dbs.append(str(coo_db))
    for db_path in dbs:
        try:
            import sqlite3
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.close()
        except Exception:
            pass


def _close_sqlite_connections():
    """Clean up persistent connections on shutdown."""
    try:
        from tools.dashboard import _global_conn
        if _global_conn is not None:
            _global_conn.close()
    except Exception:
        pass
    try:
        from devpet.tracker import DevPetTracker
    except Exception:
        pass


app = FastAPI(title="Deterministic Brain", version="2.5.0", lifespan=lifespan)
scheduler = get_scheduler()
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()
forge = Forge()
dash  = Dashboard()

def _cleanup_old_builds(max_age_days: int = 7):
    try:
        builds_dir = "builds"
        if not os.path.isdir(builds_dir):
            return
        cutoff = time.time() - max_age_days * 86400
        import shutil
        for name in os.listdir(builds_dir):
            path = os.path.join(builds_dir, name)
            if os.path.isdir(path):
                mtime = os.path.getmtime(path)
                if mtime < cutoff:
                    shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

_cleanup_old_builds()

# ── Starter knowledge seed (if KB is empty) ────────────────────────
def _seed_knowledge():
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        if bank.stats().get("total_fragments", 0) > 0:
            return
        from knowledge.ingester import KnowledgeIngester
        ingester = KnowledgeIngester()
        seeds = [
            ("React Hooks Basics", "React hooks let you use state and other React features in functional components. useState returns [value, setter]. useEffect runs after render. useContext consumes context.", "react javascript hooks frontend"),
            ("Python FastAPI Guide", "FastAPI is a modern Python web framework. Use @app.get('/') to define routes. Pydantic models for request validation. Async support with async/await.", "python fastapi api backend"),
            ("CSS Grid Layout", "CSS Grid: display:grid on container, grid-template-columns for column sizing, gap for spacing. Use grid-column and grid-row to position items.", "css layout frontend design"),
            ("Git Workflow", "Common git workflow: git pull, make changes, git add ., git commit -m 'message', git push. Use branches for features. Pull requests for code review.", "git version-control workflow"),
        ]
        for title, content, tags_str in seeds:
            fragments = ingester.ingest_text(content, title, tags_str.split())
            bank.add_fragments(fragments)
    except Exception as _e:
        import logging as _log
        _log.getLogger(__name__).warning("Knowledge seeding failed: %s", _e)

    # _seed_knowledge()

# Enable hot-reload skill watcher if env var is set
if os.environ.get("API_SKILL_WATCH", "").lower() in ("1", "true", "yes"):
    _get_skill_registry(enable_watch=True)

# Middleware
import re
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001,http://localhost:5173,http://localhost:8000").split(",")
app.add_middleware(CORSMiddleware,
    allow_origins=_cors_origins if _cors_origins[0] != "*" else ["*"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(settings_router)
app.include_router(voice_router)
app.include_router(devpets_router)
app.include_router(kairos_router)
app.include_router(evolution_router)
app.include_router(social_router)
app.include_router(media_router)
app.include_router(knowledge_router)
app.include_router(agi_router)
app.include_router(acquisition_router)

# Notifications
try:
    from api.notifications import router as notifications_router
    app.include_router(notifications_router)
except Exception:
    _api_logger.exception("Failed to load notifications router")

# COO Brain webhooks
try:
    from api.routes.coo_webhooks import router as coo_router
    app.include_router(coo_router)
except Exception as _e:
    import logging as _log
    _log.getLogger(__name__).warning("COO Brain routes not loaded: %s", _e)
    pass

# @app.get("/health") # REMOVED - duplicate, see line 1260 for active definition

# --- Integrated Frontend Mounting ---
# Mount static assets from the dashboard build
if os.path.exists("aether-dashboard/dist/assets"):
    app.mount("/assets", StaticFiles(directory="aether-dashboard/dist/assets"), name="assets")
if os.path.exists("aether-dashboard/dist"):
    app.mount("/static", StaticFiles(directory="aether-dashboard/dist"), name="static")


# ── Models ─────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    query: str
    lane_override: Optional[str] = None

class BundleRequest(BaseModel):
    bundle: str
    inputs: Dict[str, Any] = {}

class DiffRequest(BaseModel):
    old: str
    new: str
    filename: str = "file"

class FetchRequest(BaseModel):
    url: str

class RelayRequest(BaseModel):
    agent:  str
    path:   str  = "/task"
    method: str  = "POST"
    body:   Dict[str, Any] = {}
    verify: bool = False

class RegisterAgentRequest(BaseModel):
    name:     str
    base_url: str

class AutoDreamRequest(BaseModel):
    dry_run: bool = True

class DialogueRequest(BaseModel):
    text: str
    seed: Optional[int] = None


class SoulUpdateRequest(BaseModel):
    identity: Optional[Dict] = None
    agenda: Optional[Dict] = None
    context: Optional[Dict] = None
    preferences: Optional[Dict] = None
    knowledge_sources: Optional[List[str]] = None
    project_templates: Optional[List[str]] = None


class TemplateUploadRequest(BaseModel):
    name: str
    content: str


class TemplateFileRequest(BaseModel):
    filepath: str


class TemplateAnswerRequest(BaseModel):
    template_id: str
    answers: Dict[str, str] = {}


class TemplateBoilRequest(BaseModel):
    template_id: str
    answers: Dict[str, str] = {}


# ── Bundle Definition (Gap 7: validation) ──────────────────────────
class BundleDefinition(BaseModel):
    description: str = ""
    lanes: List[str] = []


# ── Caching Layer (in-memory by design — cold restart is acceptable for TTL cache) ──
class CacheManager:
    """Intelligent TTL-based caching for expensive API responses.
    Evicts oldest entries when max_size is reached.
    When DISTRIBUTED_MODE=1, delegates to Redis for cross-worker sharing.
    """
    def __init__(self, max_size: int = 500):
        self._store: Dict[str, Dict] = {}
        self._max_size = max_size
        self._lock = None

    def _get_lock(self):
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        return self._lock

    def get(self, key: str) -> Optional[Any]:
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    val = r.cache_get(key)
                    return json.loads(val) if val else None
            except Exception:
                pass
        with self._get_lock():
            if key in self._store:
                entry = self._store[key]
                if time.time() < entry["expiry"]:
                    entry["last_access"] = time.time()
                    return entry["data"]
                del self._store[key]
        return None

    def set(self, key: str, data: Any, ttl: int = 60):
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.cache_set(key, json.dumps(data, default=str), ttl)
                    return
            except Exception:
                pass
        with self._get_lock():
            if len(self._store) >= self._max_size and key not in self._store:
                oldest = min(self._store.items(), key=lambda kv: kv[1].get("last_access", kv[1]["expiry"]))
                del self._store[oldest[0]]
            self._store[key] = {
                "data": data,
                "expiry": time.time() + ttl,
                "last_access": time.time(),
            }

    def invalidate(self, key: str):
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.cache_delete(key)
                    return
            except Exception:
                pass
        with self._get_lock():
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str):
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.cache_scan_delete(prefix)
                    return
            except Exception:
                pass
        with self._get_lock():
            for k in list(self._store.keys()):
                if k.startswith(prefix):
                    del self._store[k]

    def size(self) -> int:
        if _DISTRIBUTED:
            return 0  # Redis-backed, in-memory size not meaningful
        with self._get_lock():
            return len(self._store)

_CACHE = CacheManager()

def cached_endpoint(ttl: int = 60):
    """Decorator to cache FastAPI endpoint responses."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                k_str = json.dumps(kwargs, sort_keys=True, default=str)
            except Exception:
                k_str = str(sorted(kwargs.items()))
            key = f"{func.__name__}:{k_str}"
            cached = _CACHE.get(key)
            if cached is not None:
                get_metrics().record_cache_hit()
                return cached

            get_metrics().record_cache_miss()

            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, func, *args, **kwargs)

            _CACHE.set(key, result, ttl)
            return result
        return wrapper
    return decorator


def invalidate_caches(*prefixes: str):
    """Invalidate all cache entries matching given prefixes."""
    for p in prefixes:
        _CACHE.invalidate_prefix(p)


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    try:
        result = agent.handle(req.query)
        
        # ---- Dashboard Sync ----
        try:
            from features.status_tracker import get_status_tracker
            tracker = get_status_tracker()
            chosen_skill = result.get("reasoning", {}).get("chosen_skill")
            if chosen_skill == "initialize-session":
                agent_id = result.get("task", {}).get("agent_id")
                if agent_id:
                    tracker.set_agent_status(agent_id, "online")
        except Exception as _ds:
            _api_logger.debug("Dashboard sync skipped: %s", _ds)
            
        return result if result else {"status": "ok", "final_output": {}, "knowledge_used": 0}
    except Exception as e:
        tb = traceback.format_exc()
        try:
            event_bus.emit("task_error", query=req.query, error=str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail={
            "error": str(e),
            "type": type(e).__name__,
            "traceback": tb.splitlines()[-8:],
        })


@app.post("/reason")
def reason_only(req: TaskRequest) -> Dict:
    """Run ONLY the reasoning pipeline — no skill execution."""
    task = agent.parser.parse(req.query)
    enriched = agent.router.enriched_candidates()
    text_to_id = {t: sid for sid, t in enriched}
    enriched_texts = [t for _, t in enriched]

    decision = agent.reasoner.decide(
        task=task,
        skill_candidates=enriched_texts,
        scorer_fn=agent._decision_scorer,
        constraints=agent._build_constraints(task),
        variable_domains=agent._variable_domains(task),
    )
    if decision.chosen_skill and decision.chosen_skill in text_to_id:
        decision.chosen_skill = text_to_id[decision.chosen_skill]

    # NOTE: All API keys are loaded from .env via the config module.
    # Never hardcode credentials in source files.

    return {"query": req.query, "task": task, "decision": decision.to_dict()}


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)


@app.get("/skills")
@app.get("/skills/list")
@cached_endpoint(ttl=30)
def list_skills() -> Dict:
    from orchestration.skill_registry import get_skill_registry
    sr = get_skill_registry()
    sr.discover()
    return {"skills": [s.to_dict() for s in sr.list_all()]}


# ── Bundles (Gap 7: schema validation) ─────────────────────────────
@app.get("/bundles")
def list_bundles() -> Dict[str, List[Dict]]:
    return _get_bundles_cached()


# ── Skill Chains (Gap fix: chains were never wired) ─────────────────
@app.get("/chains")
@cached_endpoint(ttl=30)
def list_chains() -> Dict:
    try:
        from features.skill_chains_loader import get_chain_status
        return get_chain_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chains/{chain_name}")
@cached_endpoint(ttl=30)
def get_chain(chain_name: str) -> Dict:
    try:
        from features.skill_chains_loader import get_chain_status
        return get_chain_status(chain_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChainRunRequest(BaseModel):
    dry_run: bool = False


@app.post("/chains/{chain_name}/run")
def execute_chain_endpoint(chain_name: str, req: ChainRunRequest = ChainRunRequest()) -> Dict:
    try:
        from features.skill_chains_loader import execute_chain
        result = execute_chain(chain_name, dry_run=req.dry_run)
        # Emit event for learning loop
        event_bus.emit("chain_executed", chain=chain_name, status=result.get("status"),
                       steps_ok=result.get("steps_ok", 0), steps_failed=result.get("steps_failed", 0))
        return result
    except Exception as e:
        return {"status": "error", "error": str(e), "chain": chain_name}


# ── Relay (Gap 8: broadcast rate limit) ────────────────────────────
@app.post("/relay")
def relay_forward(req: RelayRequest) -> Dict:
    return relay.forward(req.agent, req.path, req.body, req.method, verify_inbound=req.verify)


@app.post("/relay/broadcast")
def relay_broadcast(body: Dict) -> Dict:
    if len(relay.agents) > 10:
        raise HTTPException(status_code=400, detail="Too many registered agents for broadcast (max 10)")
    path = body.pop("path", "/task")
    return relay.broadcast(path, body)


@app.get("/relay/agents")
def relay_agents() -> Dict:
    return {"agents": relay.agents}


@app.post("/relay/register")
def relay_register(req: RegisterAgentRequest) -> Dict:
    relay.register(req.name, req.base_url)
    return {"registered": req.name, "url": req.base_url, "agents": relay.agents}


# ── Forge ──────────────────────────────────────────────────────────
@app.post("/forge/diff")
def diff(req: DiffRequest) -> Dict:
    return forge_diff(req.old, req.new, req.filename)


@app.post("/forge/validate")
def validate(body: Dict) -> Dict:
    return forge.validate_skill(body.get("path", ""))


@app.post("/forge/fetch")
def fetch_url(req: FetchRequest) -> Dict:
    return web_fetch(req.url)


# ── Dashboard ──────────────────────────────────────────────────────
@app.get("/dashboard/feed")
@cached_endpoint(ttl=5)
def feed() -> Dict:
    return {"events": dash.recent_events(50)}


@app.post("/dashboard/feed-clear")
def feed_clear() -> Dict:
    dash.clear_events()
    return {"status": "ok"}


@app.get("/dashboard/audit")
@cached_endpoint(ttl=5)
def audit() -> Dict:
    return {"events": dash.audit_feed()}


@app.get("/dashboard/stats")
@cached_endpoint(ttl=10)
def stats() -> Dict:
    return {"bundles": dash.bundle_stats(), "skills": dash.skill_stats()}


@app.get("/dashboard/middleware-stats")
def middleware_stats_route() -> Dict:
    return {"routes": get_route_stats()}


# ── AutoDream ──────────────────────────────────────────────────────
@app.post("/autodream")
def autodream(req: AutoDreamRequest) -> Dict:
    return run_autodream(dry_run=req.dry_run)


@app.post("/autodream/run")
def autodream_run() -> Dict:
    return run_autodream(dry_run=False)


@app.get("/autodream/status")
@cached_endpoint(ttl=30)
def autodream_status() -> Dict:
    path = os.environ.get("AUTODREAM_STATUS_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), ".autodream_last_run.json"))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.loads(f.read())
    return {"status": "never_run"}


# ── Soul ───────────────────────────────────────────────────────────
@app.get("/soul")
@cached_endpoint(ttl=30)
def soul_get() -> Dict:
    from brain.soul import get_soul
    s = get_soul()
    return {
        "loaded": s.name != "",
        "summary": s.summary(),
        "identity": {"name": s.name, "role": s.role, "timezone": s.timezone, "pronouns": s.pronouns},
        "agenda": {"mission": s.mission, "goals": s.goals, "anti_goals": s.anti_goals, "autonomous_directives": s.autonomous_directives},
        "context": {"expertise": s.expertise, "learning": s.learning, "notes": s.notes, "stack": {"languages": s.stack_languages, "frameworks": s.stack_frameworks, "tools": s.stack_tools}},
        "preferences": {"code_style": s.code_style, "naming": s.naming, "testing": s.testing, "deploy": s.deploy, "communication": {"verbosity": s.verbosity, "tone": s.tone}},
        "knowledge_sources": s.knowledge_sources,
        "project_templates": s.project_templates,
        "meta": {"version": s.meta_version, "created": s.meta_created, "updated": s.meta_updated, "sessions": s.meta_sessions},
    }


@app.post("/soul")
def soul_update(req: SoulUpdateRequest) -> Dict:
    invalidate_caches("soul_get:")
    from brain.soul import get_soul
    s = get_soul()
    if req.identity:
        for k, v in req.identity.items():
            if hasattr(s, k):
                setattr(s, k, v)
    if req.agenda:
        if "mission" in req.agenda:
            s.mission = req.agenda["mission"]
        if "goals" in req.agenda:
            s.goals = req.agenda["goals"] if req.agenda["goals"] is not None else []
        if "anti_goals" in req.agenda:
            s.anti_goals = req.agenda["anti_goals"] if req.agenda["anti_goals"] is not None else []
        if "autonomous_directives" in req.agenda:
            s.autonomous_directives = req.agenda["autonomous_directives"] if req.agenda["autonomous_directives"] is not None else []
    if req.context:
        ctx = req.context
        if "expertise" in ctx:
            s.expertise = ctx["expertise"] if ctx["expertise"] is not None else []
        if "learning" in ctx:
            s.learning = ctx["learning"] if ctx["learning"] is not None else []
        if "notes" in ctx:
            s.notes = ctx.get("notes", s.notes)
        if "stack" in ctx:
            stack = ctx["stack"]
            if "languages" in stack:
                s.stack_languages = stack["languages"] if stack["languages"] is not None else []
            if "frameworks" in stack:
                s.stack_frameworks = stack["frameworks"] if stack["frameworks"] is not None else []
            if "tools" in stack:
                s.stack_tools = stack["tools"] if stack["tools"] is not None else []
    if req.preferences:
        pref = req.preferences
        for k, v in pref.items():
            if k == "communication":
                if "verbosity" in v:
                    s.verbosity = v["verbosity"]
                if "tone" in v:
                    s.tone = v["tone"]
            elif hasattr(s, k):
                setattr(s, k, v)
    if req.knowledge_sources is not None:
        s.knowledge_sources = req.knowledge_sources
    if req.project_templates is not None:
        s.project_templates = req.project_templates
    s.save()
    return {"status": "ok", "summary": s.summary()}


@app.post("/soul/pulse")
def soul_pulse() -> Dict:
    from brain.soul import get_soul
    s = get_soul()
    result = s.pulse()
    return result


# ── Templates ──────────────────────────────────────────────────────
@app.get("/templates")
def templates_list() -> Dict:
    from features.template_builder import get_template_builder
    tb = get_template_builder()
    return {"templates": [t.to_dict() for t in tb.list_all()]}


@app.post("/templates/upload")
def templates_upload(req: TemplateUploadRequest) -> Dict:
    from features.template_builder import get_template_builder
    tb = get_template_builder()
    t = tb.upload_text(req.name, req.content)
    return {"template": t.to_dict(), "questions": len(t.questions)}


@app.post("/templates/file")
def templates_file(req: TemplateFileRequest) -> Dict:
    from features.template_builder import get_template_builder
    tb = get_template_builder()
    t = tb.upload_file(req.filepath)
    if not t:
        raise HTTPException(status_code=404, detail="file not found")
    return {"template": t.to_dict(), "questions": len(t.questions)}


@app.post("/templates/answer")
def templates_answer(req: TemplateAnswerRequest) -> Dict:
    from features.template_builder import get_template_builder
    tb = get_template_builder()
    result = tb.answer(req.template_id, req.answers)
    if result is None:
        raise HTTPException(status_code=404, detail="template not found")
    return {"template_id": req.template_id, "generated": result}


@app.post("/templates/boil")
def templates_boil(req: TemplateBoilRequest) -> Dict:
    from features.template_builder import get_template_builder
    from brain.soul import get_soul
    tb = get_template_builder()
    s = get_soul()
    task = tb.boil(req.template_id, req.answers, soul_context=s.to_context())
    if task.get("error"):
        raise HTTPException(status_code=404, detail=task["error"])
    result = agent.handle(task["query"])
    return {
        "template_id": req.template_id,
        "generated": task["generated_content"][:2000],
        "task_result": result,
    }


@app.delete("/templates/{template_id}")
def templates_delete(template_id: str) -> Dict:
    from features.template_builder import get_template_builder
    tb = get_template_builder()
    if tb.delete(template_id):
        return {"deleted": template_id}
    raise HTTPException(status_code=404, detail="template not found")


# ── Static assets ──────────────────────────────────────────────────
@app.get("/ui/{filename}")
def serve_ui_file(filename: str) -> FileResponse:
    base = os.path.abspath("ui")
    path = os.path.abspath(os.path.join("ui", filename))
    if not path.startswith(base):
        raise HTTPException(status_code=403, detail="path traversal blocked")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


@app.get("/media/serve/{filename}")
def serve_media_file(filename: str) -> FileResponse:
    """Serve generated images/videos from the exports directory."""
    base = os.path.abspath("exports")
    if not os.path.exists(base):
        os.makedirs(base, exist_ok=True)
    path = os.path.abspath(os.path.join(base, filename))
    if not path.startswith(base):
        raise HTTPException(status_code=403, detail="path traversal blocked")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


@app.get("/preview/{build_id}/{filename:path}")
def serve_build_file(build_id: str, filename: str) -> FileResponse:
    base = os.path.abspath("builds")
    path = os.path.abspath(os.path.join("builds", build_id, filename))
    if not path.startswith(base):
        raise HTTPException(status_code=403, detail="path traversal blocked")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="build file not found")
    return FileResponse(path)


@app.get("/preview/{build_id}")
def serve_build_index(build_id: str) -> FileResponse:
    build_dir = os.path.join("builds", build_id)
    if not os.path.exists(build_dir):
        raise HTTPException(status_code=404, detail="build not found")
    index_path = os.path.join(build_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    alt = os.path.join(build_dir, "index.htm")
    if os.path.exists(alt):
        return FileResponse(alt)
    files = [f for f in os.listdir(build_dir) if os.path.isfile(os.path.join(build_dir, f))]
    if not files:
        raise HTTPException(status_code=404, detail="empty build")
    return FileResponse(os.path.join(build_dir, files[0]))


@app.get("/llm-status")
@cached_endpoint(ttl=30)
def llm_status() -> Dict:
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    enabled = os.getenv("LLM_ENABLED", "").lower() != "false" and (has_openrouter or has_anthropic or has_openai)
    provider = "openrouter" if has_openrouter else "anthropic" if has_anthropic else "none"
    try:
        from tools.llm.openrouter_client import get_client
        available = get_client().available
    except Exception:
        available = False
    return {
        "enabled": enabled,
        "available": available,
        "provider": provider,
        "has_keys": {"openrouter": has_openrouter, "anthropic": has_anthropic, "openai": has_openai},
    }


# ── Betting ─────────────────────────────────────────────────────────
@app.get("/betting/sheet")
def betting_sheet(sport: str = "basketball_nba", bankroll: float = 1000.0, min_ev: float = 0.01) -> Dict:
    from features.betting_engine import get_bet_sheet
    return get_bet_sheet().build_sheet(sport, bankroll, min_ev)


@app.get("/betting/odds")
def betting_odds(sport: str = "basketball_nba") -> Dict:
    from features.finance_modules import get_odds
    lines = get_odds().fetch_odds(sport)
    return {"lines": [line.to_dict() for line in lines], "count": len(lines)}


@app.get("/betting/kelly")
def betting_kelly(sport: str = "basketball_nba", bankroll: float = 1000.0) -> Dict:
    from features.finance_modules import get_odds
    engine = get_odds()
    lines = engine.fetch_odds(sport)
    kelly = engine.calculate_kelly(lines, bankroll)
    return {"bankroll": bankroll, "recommendations": kelly}


@app.get("/betting/backtest")
def betting_backtest(
    kelly_frac: float = 0.25,
    min_edge: float = 0.0,
    market: str = "ml",
    starting_bankroll: float = 10000.0,
    n_sims: int = 100,
    use_synthetic: int = 0,
) -> Dict:
    from backtesting.backtest_engine import BacktestEngine
    import os
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "datasets")
    engine = BacktestEngine(data_dir=data_dir)
    result = engine.backtest_kelly(
        kelly_frac=kelly_frac,
        min_edge=min_edge,
        market=market,
        starting_bankroll=starting_bankroll,
        use_synthetic=bool(use_synthetic),
    )
    if n_sims > 0:
        mc = engine.monte_carlo(
            lambda: engine.backtest_kelly(kelly_frac, min_edge, market, starting_bankroll, bool(use_synthetic)),
            n_sims=n_sims,
        )
        result.sims.update(mc)
    report = engine.report(result)
    return {
        "result": result.to_dict(),
        "report": report,
        "monte_carlo": result.sims,
    }


@app.get("/betting/prizepicks")
def betting_prizepicks(market: str = "all", min_line: float = 0) -> Dict:
    from features.prizepicks_scraper import get_prizepicks_scraper
    scraper = get_prizepicks_scraper()
    props = scraper.fetch()
    if market != "all":
        props = [p for p in props if p.market.lower() == market.lower()]
    if min_line > 0:
        props = [p for p in props if p.line >= min_line]
    by_market = {}
    for p in props:
        if p.market not in by_market:
            by_market[p.market] = []
        by_market[p.market].append(p.to_dict())
    return {
        "mode": scraper.mode,
        "total_props": len(props),
        "markets": list(by_market.keys()),
        "by_market": {k: len(v) for k, v in by_market.items()},
        "props": [p.to_dict() for p in props],
    }


# ── Integrations status ────────────────────────────────────────────
@app.get("/integrations")
@cached_endpoint(ttl=60)
def integrations_status() -> Dict:
    return {
        "apis": {
            "openrouter": {"configured": bool(os.getenv("OPENROUTER_API_KEY")), "label": "OpenRouter (Multi-Model)"},
            "anthropic": {"configured": bool(os.getenv("ANTHROPIC_API_KEY")), "label": "Anthropic (Claude)"},
            "openai": {"configured": bool(os.getenv("OPENAI_API_KEY")), "label": "OpenAI (GPT-4o, o3)"},
            "deepseek": {"configured": bool(os.getenv("DEEPSEEK_API_KEY")), "label": "DeepSeek"},
            "gemini": {"configured": bool(os.getenv("GEMINI_API_KEY")), "label": "Google Gemini"},
            "odds_api": {"configured": bool(os.getenv("ODDS_API_KEY")), "label": "The Odds API (Sports)"},
            "tavily": {"configured": bool(os.getenv("TAVILY_API_KEY")), "label": "Tavily (Web Search)"},
            "github": {"configured": bool(os.getenv("GITHUB_TOKEN")), "label": "GitHub"},
            "qdrant": {"configured": bool(os.getenv("QDRANT_URL")), "label": "Qdrant (Vector DB)"},
            "neo4j": {"configured": bool(os.getenv("NEO4J_URI")), "label": "Neo4j (Knowledge Graph)"},
            "stripe": {"configured": bool(os.getenv("STRIPE_SECRET_KEY")), "label": "Stripe (Payments)"},
            "reddit": {"configured": bool(os.getenv("REDDIT_CLIENT_ID")), "label": "Reddit API"},
            "discord": {"configured": bool(os.getenv("DISCORD_BOT_TOKEN")), "label": "Discord Bot"},
        },
        "features": {
            "browser": {"available": True, "label": "Web Browser"},
            "planner": {"available": True, "label": "Task Planner / Scheduler"},
            "social": {"available": bool(os.getenv("DISCORD_BOT_TOKEN") or os.getenv("SLACK_WEBHOOK_URL")), "label": "Social Media Scheduler"},
            "saas_builder": {"available": True, "label": "SaaS Builder"},
            "skill_expander": {"available": bool(os.getenv("GITHUB_TOKEN")), "label": "Auto Skill Expansion"},
            "betting": {"available": bool(os.getenv("ODDS_API_KEY")), "label": "Sports Betting Engine"},
            "trading": {"available": bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("ANTHROPIC_API_KEY")), "label": "Trading Engine"},
            "news": {"available": bool(os.getenv("NEWSAPI_KEY") or os.getenv("GNEWS_API_KEY") or os.getenv("WORLDNEWS_API_KEY")), "label": "News Feed (HN + Dev.to)"},
        },
        "configured_count": sum(1 for v in [
            os.getenv("OPENROUTER_API_KEY"), os.getenv("ANTHROPIC_API_KEY"),
            os.getenv("OPENAI_API_KEY"), os.getenv("DEEPSEEK_API_KEY"),
            os.getenv("GEMINI_API_KEY"), os.getenv("ODDS_API_KEY"),
            os.getenv("TAVILY_API_KEY"), os.getenv("GITHUB_TOKEN"),
            os.getenv("QDRANT_URL"), os.getenv("NEO4J_URI"),
            os.getenv("STRIPE_SECRET_KEY"), os.getenv("REDDIT_CLIENT_ID"),
            os.getenv("DISCORD_BOT_TOKEN"),
        ] if v),
    }


# ── Smart Chat (intent routing) ────────────────────────────────────
class ChatRequest(BaseModel):
    text: str


@app.post("/chat")
def chat_smart(req: ChatRequest) -> Dict:
    from features.chat_router import handle_chat
    return handle_chat(req.text)


# ── Hermes Proxy ───────────────────────────────────────────────
@app.get("/hermes/status")
def hermes_status() -> Dict:
    """Check if hermes is reachable."""
    try:
        import httpx
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{HERMES_URL}/api/status")
            if resp.status_code >= 400:
                return {"connected": False, "status": {"error": f"Hermes returned {resp.status_code}"}}
            return {"connected": True, "status": resp.json()}
    except Exception:
        return {"connected": False, "status": None}


@app.post("/hermes/chat")
def hermes_chat(req: ChatRequest) -> Dict:
    """Send a message to hermes for processing."""
    try:
        import httpx
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{HERMES_URL}/api/chat", json={"text": req.text})
            if resp.status_code >= 400:
                return {"_error": f"Hermes returned {resp.status_code}", "text": req.text, "fallback": True}
            return resp.json()
    except Exception as e:
        return {"_error": f"Hermes unavailable: {str(e)}", "text": req.text, "fallback": True}


@app.get("/hermes/skills")
def hermes_skills() -> Dict:
    """List skills from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/skills")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "skills": []}


@app.post("/hermes/skills/{skill_id}/toggle")
def hermes_toggle_skill(skill_id: str) -> Dict:
    """Toggle a skill in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/skills/{skill_id}/toggle")
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}


@app.get("/hermes/cron")
def hermes_cron() -> Dict:
    """List cron jobs from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/cron")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "cron": []}


@app.post("/hermes/cron")
def hermes_create_cron(body: Dict) -> Dict:
    """Create a cron job in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/cron", json=body)
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}


@app.get("/hermes/sessions")
def hermes_sessions() -> Dict:
    """List active sessions from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/sessions")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "sessions": []}


@app.get("/hermes/sessions/{session_id}/messages")
def hermes_session_messages(session_id: str) -> Dict:
    """Get messages from a hermes session."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/sessions/{session_id}/messages")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "messages": []}


@app.get("/hermes/models")
def hermes_models() -> Dict:
    """List available models from hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{HERMES_URL}/api/models")
            return resp.json()
    except Exception as e:
        return {"_error": str(e), "models": []}


@app.post("/hermes/models/assign")
def hermes_assign_model(body: Dict) -> Dict:
    """Assign a model in hermes."""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(f"{HERMES_URL}/api/models/assign", json=body)
            return resp.json()
    except Exception as e:
        return {"_error": str(e)}


# ── Local Model (Gemma-4 via llama.cpp) ────────────────────────
@app.get("/models/local/status")
def local_model_status() -> Dict:
    """Check if the local Gemma-4 model is running."""
    try:
        import httpx
        with httpx.Client(timeout=3) as client:
            resp = client.get(f"{LOCAL_MODEL_URL}/v1/models")
            if resp.status_code >= 400:
                return {"connected": False, "models": []}
            return {"connected": True, "models": resp.json()}
    except Exception:
        return {"connected": False, "models": []}


@app.post("/models/local/chat")
def local_model_chat(req: ChatRequest) -> Dict:
    """Chat directly with the local Gemma-4 model."""
    try:
        import httpx
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{LOCAL_MODEL_URL}/v1/chat/completions", json={
                "model": LOCAL_MODEL_NAME,
                "messages": [{"role": "user", "content": req.text}],
                "stream": False,
            })
            if resp.status_code >= 400:
                return {"_error": f"Model returned {resp.status_code}"}
            return resp.json()
    except Exception as e:
        return {"_error": f"Model unavailable: {str(e)}"}


@app.post("/models/local/proxy")
async def local_model_proxy(request: Request) -> Dict:
    """Proxy endpoint for local model - used by LLM router for deterministic tasks."""
    try:
        # Forward the request to the local model server
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Get the raw body and forward it
            body = await request.body()
            resp = await client.post(
                f"{LOCAL_MODEL_URL}/v1/chat/completions",
                content=body,
                headers={"Content-Type": "application/json"}
            )
            
            if resp.status_code >= 400:
                return {"_error": f"Local model returned {resp.status_code}", "details": resp.text}
            
            return resp.json()
    except Exception as e:
        return {"_error": f"Local model proxy failed: {str(e)}"}


# ── Tool Registration (command-code, opencode) ─────────────────
_REGISTERED_TOOLS: Dict[str, Dict] = {}


@app.post("/tools/register")
def register_tool(body: Dict) -> Dict:
    """Register a tool (command-code, opencode, etc.)."""
    name = body.get("name")
    tool_type = body.get("type", "subprocess")
    config = body.get("config", {})
    _REGISTERED_TOOLS[name] = {"type": tool_type, "config": config}
    return {"status": "ok", "registered": name, "tools": list(_REGISTERED_TOOLS.keys())}


@app.get("/tools")
def list_tools() -> Dict:
    """List registered tools."""
    tools = []
    for name, info in _REGISTERED_TOOLS.items():
        tools.append({"name": name, "type": info["type"], "status": "registered"})
    return {"tools": tools}


@app.post("/tools/{tool_name}/execute")
def execute_tool(tool_name: str, body: Dict) -> Dict:
    """Execute a registered tool."""
    if tool_name not in _REGISTERED_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not registered")
    
    tool = _REGISTERED_TOOLS[tool_name]
    if tool["type"] == "subprocess":
        import subprocess
        cmd = tool["config"].get("command", [])
        if not cmd:
            raise HTTPException(status_code=400, detail="No command configured for tool")
        try:
            result = subprocess.run(
                cmd,
                input=body.get("input", ""),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return {
                "tool": tool_name,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:10000],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"tool": tool_name, "error": "Tool execution timed out (60s)"}
        except Exception as e:
            return {"tool": tool_name, "error": str(e)}
    else:
        raise HTTPException(status_code=400, detail=f"Tool type '{tool['type']}' not supported")


# ── WebSocket Chat ─────────────────────────────────────────────
@app.websocket("/ws/chat")
async def chat_websocket(ws: WebSocket):
    """WebSocket endpoint for streaming chat with hermes."""
    await ws.accept()
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            text = data.get("text", "")
            
            # Forward to hermes and stream response
            try:
                import httpx
                async with httpx.AsyncClient(timeout=120) as client:
                    async with client.stream(
                        "POST",
                        f"{HERMES_URL}/api/chat/stream",
                        json={"text": text}
                    ) as resp:
                        async for chunk in resp.aiter_text():
                            await ws.send_text(chunk)
            except Exception as e:
                await ws.send_text(json.dumps({"_error": str(e), "text": text, "fallback": True}))
    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await ws.close()
        except Exception:
            pass


# ── Dialogue ───────────────────────────────────────────────────────
@app.post("/dialogue/process")
def dialogue_process(req: DialogueRequest) -> Dict:
    from dialogue import create_dialogue_pipeline

    pipeline = create_dialogue_pipeline(seed=req.seed)
    result = pipeline.process(req.text)
    pipeline.close()

    event_bus.emit("dialogue_turn",
        input_text=req.text, intent=result.intent,
        response=result.response, state=result.state)

    return {
        "response": result.response, "intent": result.intent,
        "confidence": result.intent_confidence, "slots": result.slots,
        "state": result.state, "action": result.action,
        "session_id": result.session_id,
    }


# ── GitHub ─────────────────────────────────────────────────────────
@app.get("/github/search")
def github_search(q: str = "", per_page: int = 10) -> Dict:
    from features.github_manager import get_github
    gh = get_github()
    repos = gh.search_repos(q, per_page)
    return {"repos": [r.to_dict() for r in repos]}


@app.post("/github/clone")
def github_clone(owner: str = "", repo: str = "") -> Dict:
    from features.github_manager import get_github
    gh = get_github()
    path = gh.clone(owner, repo)
    return {"cloned": path is not None, "path": path or ""}


@app.post("/github/expand-skills")
def github_expand_skills(max_downloads: int = 5) -> Dict:
    from features.github_manager import get_github
    gh = get_github()
    return gh.download_skill_packs("skill_packs")


# ── Planner ────────────────────────────────────────────────────────
@app.get("/planner/tasks")
@cached_endpoint(ttl=10)
def planner_tasks() -> Dict:
    from features.planner import get_planner
    p = get_planner()
    return {"tasks": [t.to_dict() for t in p.list_all()]}


@app.post("/planner/tasks")
def planner_add(title: str = "", query: str = "", schedule: str = "now",
                recurrence: str = "", priority: int = 0, max_runs: int = 0,
                tags: str = "") -> Dict:
    from features.planner import get_planner
    p = get_planner()
    t = p.add(title, query, schedule, recur=recurrence, priority=priority,
              max_runs=max_runs, tags=tags.split(",") if tags else [])
    return {"task": t.to_dict()}


@app.delete("/planner/tasks/{task_id}")
def planner_delete(task_id: str) -> Dict:
    from features.planner import get_planner
    return {"deleted": get_planner().delete(task_id)}


@app.get("/planner/timeline")
@cached_endpoint(ttl=10)
def planner_timeline(hours: int = 24) -> Dict:
    from features.planner import get_planner
    return {"timeline": get_planner().get_timeline(hours)}


@app.post("/planner/generate-from-soul")
def planner_generate_from_soul() -> Dict:
    from features.planner import get_planner
    from brain.soul import get_soul
    tasks = get_planner().generate_from_soul(get_soul().goals)
    return {"generated": len(tasks), "tasks": [t.to_dict() for t in tasks]}


@app.post("/planner/run-due")
def planner_run_due() -> Dict:
    from features.planner import get_planner
    p = get_planner()
    due = p.get_due()
    results = []
    for t in due[:5]:
        p.mark_running(t.id)
        try:
            r = agent.handle(t.query)
            p.mark_done(t.id, r)
            results.append({"id": t.id, "status": "ok", "result": r.get("status")})
        except Exception as e:
            p.mark_failed(t.id, str(e))
            results.append({"id": t.id, "status": "failed", "error": str(e)})
    return {"ran": len(results), "results": results}


# ── News / Finance ─────────────────────────────────────────────────
@app.get("/news")
@cached_endpoint(ttl=120)
def news_feed() -> Dict:
    from features.finance_modules import get_news
    items = get_news().fetch_all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@app.get("/odds")
@cached_endpoint(ttl=60)
def odds_feed(sport: str = "basketball_nba") -> Dict:
    from features.finance_modules import get_odds
    lines = get_odds().fetch_odds(sport)
    return {"lines": [line.to_dict() for line in lines], "count": len(lines)}


@app.post("/odds/value")
def odds_value(sport: str = "basketball_nba", bankroll: float = 1000.0) -> Dict:
    from features.finance_modules import get_odds
    engine = get_odds()
    lines = engine.fetch_odds(sport)
    value = engine.find_value(lines)
    kelly = engine.calculate_kelly(value, bankroll)
    return {"value_bets": len(value), "kelly": kelly}


# @app.get("/trading/price") # REMOVED - duplicate, see line ~1331 for active cached definition


@app.post("/trading/evaluate")
def trading_evaluate(symbol: str = "AAPL", prices: str = "") -> Dict:
    from features.finance_modules import get_trading
    engine = get_trading()
    if prices:
        price_list = [float(x) for x in prices.split(",")]
    else:
        current = engine.fetch_price(symbol) or 100
        price_list = [current] * 25
    signal = engine.evaluate(symbol, price_list)
    return signal.to_dict() if signal else {"action": "NONE"}


# @app.get("/trading/balance") # REMOVED - duplicate, see line ~1306 for active definition


# ── Social ─────────────────────────────────────────────────────────
@app.get("/social/posts")
def social_posts() -> Dict:
    from features.social_scheduler import get_social
    return {"posts": [p.to_dict() for p in get_social().list_all()]}


@app.post("/social/schedule")
def social_schedule(platform: str = "twitter", content: str = "",
                    delay_minutes: int = 0, media_url: str = "",
                    tags: str = "") -> Dict:
    from features.social_scheduler import get_social
    p = get_social().schedule(platform, content, delay_minutes,
                               media_url, tags.split(",") if tags else [])
    return {"post": p.to_dict()}


@app.post("/social/post-due")
def social_post_due() -> Dict:
    from features.social_scheduler import get_social
    s = get_social()
    due = s.get_due()
    posted = 0
    for post in due:
        result = s.post_via_webhook(post)
        if result.get("status") == "ok":
            s.mark_posted(post.id, result)
            posted += 1
        else:
            s.mark_failed(post.id, result.get("error", ""))
    return {"posted": posted, "total_due": len(due)}


@app.post("/social/webhook")
def social_set_webhook(platform: str = "discord", url: str = "") -> Dict:
    from features.social_scheduler import get_social
    get_social().set_webhook(platform, url)
    return {"platform": platform, "url_set": bool(url)}


# ── SaaS Builder ───────────────────────────────────────────────────
@app.get("/saas/projects")
def saas_projects() -> Dict:
    from features.saas_builder import get_saas_builder
    return {"projects": [p.to_dict() for p in get_saas_builder().list_all()]}


@app.post("/saas/create")
def saas_create(name: str = "", idea: str = "", tech_stack: str = "") -> Dict:
    from features.saas_builder import get_saas_builder
    stack = tech_stack.split(",") if tech_stack else None
    p = get_saas_builder().create_project(name, idea, stack)
    return {"project": p.to_dict()}


@app.post("/saas/advance")
def saas_advance(project_id: str = "") -> Dict:
    from features.saas_builder import get_saas_builder
    p = get_saas_builder().advance_stage(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return {"project": p.to_dict()}


@app.post("/saas/stripe")
def saas_stripe(project_id: str = "", price_usd: int = 9) -> Dict:
    from features.saas_builder import get_saas_builder
    result = get_saas_builder().setup_stripe(project_id, price_usd)
    return result


# ── Skill Expander ─────────────────────────────────────────────────
@app.post("/skills/expand")
def skills_expand(max_downloads: int = 3) -> Dict:
    from features.skill_expander import get_expander
    result = get_expander().expand(max_downloads)
    return result


@app.get("/skills/expand-stats")
def skills_expand_stats() -> Dict:
    from features.skill_expander import get_expander
    return get_expander().get_stats()


# ── Enhanced Betting ────────────────────────────────────────────────
@app.get("/betting/enhanced")
def betting_enhanced(sport: str = "basketball_nba", bankroll: float = 1000.0) -> Dict:
    from features.betting_enhanced import get_enhanced_betting
    return get_enhanced_betting().generate(sport, bankroll)


@app.get("/betting/trends")
def betting_trends(player: str = "LeBron James", market: str = "points", line: float = 25.0) -> Dict:
    from features.betting_enhanced import SportsDataFeed, TrendAnalyzer
    stats = SportsDataFeed().fetch_nba_player(player)
    if not stats:
        return {"error": "player not found"}
    trends = TrendAnalyzer().analyze(stats, market, line)
    return {"player": player, "stats": stats.to_dict(), "trends": trends}


@app.get("/betting/circadian")
def betting_circadian(team: str = "Lakers", opponent: str = "Celtics", game_time: str = "19:00") -> Dict:
    from features.betting_enhanced import CircadianAnalyzer
    return CircadianAnalyzer().analyze(team, opponent, game_time)


@app.post("/betting/formulas")
def betting_upload_formula(name: str = "", expression: str = "", description: str = "") -> Dict:
    from features.betting_enhanced import FormulaEngine
    if not name or not expression:
        raise HTTPException(status_code=400, detail="name and expression required")
    return FormulaEngine().upload(name, expression, description)


@app.get("/betting/formulas")
def betting_list_formulas() -> Dict:
    from features.betting_enhanced import FormulaEngine
    return {"formulas": FormulaEngine().list_all()}


@app.delete("/betting/formulas/{formula_id}")
def betting_delete_formula(formula_id: str) -> Dict:
    from features.betting_enhanced import FormulaEngine
    if FormulaEngine().delete(formula_id):
        return {"deleted": formula_id}
    raise HTTPException(status_code=404, detail="formula not found")


# ── Autonomy & Dream ────────────────────────────────────────────────
@app.post("/autonomy/dream")
def autonomy_dream() -> Dict:
    from features.autonomy import get_autonomy
    return get_autonomy().force_dream()


@app.get("/autonomy/status")
def autonomy_status() -> Dict:
    from features.autonomy import get_autonomy
    return get_autonomy().get_status()


@app.post("/autonomy/tick")
def autonomy_tick() -> Dict:
    from features.autonomy import get_autonomy
    return get_autonomy().tick()


# ── Scheduler ──────────────────────────────────────────────────────
@app.get("/scheduler/tasks")
@cached_endpoint(ttl=10)
def scheduler_tasks() -> Dict:
    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        
        # Return task definitions directly from internal storage
        # This bypasses any issues with APScheduler job access
        tasks = []
        try:
            # First try the normal way
            tasks = s.list_tasks()
        except Exception as list_err:
            # If that fails, build tasks directly from internal _tasks dict
            import logging
            logging.getLogger(__name__).warning(f"list_tasks failed, using fallback: {list_err}")
            for name, task_def in s._tasks.items():
                tasks.append({
                    "name": task_def.name,
                    "skill": task_def.skill,
                    "trigger": task_def.trigger_type,
                    "cron_expr": task_def.cron_expr,
                    "interval_seconds": task_def.interval_seconds,
                    "enabled": task_def.enabled,
                    "notify_email": task_def.notify_email is not None,
                    "notify_webhook": task_def.notify_webhook is not None,
                    "next_run": None
                })
        
        return {"tasks": tasks, "running": s.is_running()}
    except Exception as e:
        import traceback
        detail = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=detail)

@app.post("/scheduler/run-due")
def scheduler_run_due() -> Dict:
    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        if s._executor_callback is None:
            from orchestration.dca_engine import DeterministicCodingAgent as _DCA
            _dca_agent = _DCA()
            s._executor_callback = lambda skill, inputs: _dca_agent.handle(f"run {skill} with {inputs}")
        # Trigger APScheduler to check for due jobs
        jobs = s._aps_scheduler.get_jobs() if s._aps_scheduler else []
        ran = 0
        for job in jobs:
            try:
                job.modify(next_run_time=None)  # Force immediate run
                ran += 1
            except Exception:
                pass
        
        # Add notification for job run
        try:
            from api.notifications import add_notification
            add_notification(
                title="Scheduled Jobs Executed",
                message=f"Run due: {ran} jobs triggered",
                category="job",
                details={"jobs_triggered": ran, "total_jobs": len(jobs)}
            )
        except Exception:
            _api_logger.warning("Failed to add notification for scheduled jobs")
        
        return {"ran": ran, "total_jobs": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scheduler/tasks")
def scheduler_add_task(req: Dict) -> Dict:
    """Add a new cron/interval task to the scheduler."""
    try:
        from features.scheduler import get_scheduler, TaskDefinition
        s = get_scheduler()
        task = TaskDefinition(
            name=req["name"],
            skill=req["skill"],
            trigger_type=req.get("trigger_type", "cron"),
            cron_expr=req.get("cron_expr"),
            interval_seconds=req.get("interval_seconds"),
            inputs=req.get("inputs", {}),
            enabled=req.get("enabled", True),
        )
        name = s.add_task(task)
        return {"status": "ok", "name": name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/scheduler/tasks/{name}/toggle")
def scheduler_toggle_task(name: str) -> Dict:
    """Toggle a task's enabled state (enable if disabled, disable if enabled)."""
    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        return s.toggle_task(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/scheduler/tasks/{name}")
def scheduler_delete_task(name: str) -> Dict:
    """Remove a task from the scheduler permanently."""
    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        removed = s.remove_task(name)
        if removed:
            return {"status": "ok", "name": name}
        raise HTTPException(status_code=404, detail=f"Task not found: {name}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health ──────────────────────────────────────────────────────────
@app.get("/health")
def health_check() -> Dict:
    return {"status": "ok", "ts": time.time(), "version": "2.5.0", "cache_size": _CACHE.size()}


# ── System Status (Comprehensive 24/7 Monitoring) ───────────────────
@app.get("/system/status")
@cached_endpoint(ttl=10)
def system_status() -> Dict:
    """Comprehensive system status for 24/7 monitoring"""
    import requests
    
    status = {
        "timestamp": datetime.now().isoformat(),
        "mode": "24/7 Autonomous",
        "version": "2.5.0",
        "uptime": time.time(),
        "components": {},
        "jobs": {},
        "notifications": {"unread": 0, "recent": []},
        "health_score": 100
    }
    
    # Check scheduler
    try:
        from features.scheduler import get_scheduler
        s = get_scheduler()
        task_count = len(s._tasks)
        enabled_count = sum(1 for t in s._tasks.values() if t.enabled)
        status["components"]["scheduler"] = {
            "status": "online",
            "total_tasks": task_count,
            "enabled": enabled_count,
            "running": s.is_running()
        }
        status["jobs"]["scheduled"] = {"count": task_count, "enabled": enabled_count}
    except Exception as e:
        status["components"]["scheduler"] = {"status": "error", "error": str(e)[:50]}
        status["health_score"] -= 10
    
    # Check knowledge bank
    try:
        from knowledge.bank import get_knowledge_bank
        kb = get_knowledge_bank()
        stats = kb.get_stats()
        status["components"]["knowledge"] = {
            "status": "online",
            "snippets": stats.get("snippets", 0),
            "fragments": stats.get("total_fragments", 0)
        }
        status["jobs"]["knowledge"] = {"snippets": stats.get("snippets", 0)}
    except Exception as e:
        status["components"]["knowledge"] = {"status": "error", "error": str(e)[:50]}
        status["health_score"] -= 5
    
    # Check betting engine
    try:
        r = requests.get(f"http://localhost:{_API_PORT}/betting/odds", timeout=5)
        if r.status_code == 200:
            data = r.json()
            status["components"]["betting"] = {"status": "online", "odds_count": data.get("count", 0)}
            status["jobs"]["betting"] = {"odds": data.get("count", 0)}
    except:
        status["components"]["betting"] = {"status": "offline"}
    
    # Check news
    try:
        r = requests.get(f"http://localhost:{_API_PORT}/news", timeout=10)
        if r.status_code == 200:
            data = r.json()
            status["components"]["news"] = {"status": "online", "items": len(data.get("items", []))}
            status["jobs"]["news"] = {"items": len(data.get("items", []))}
    except:
        status["components"]["news"] = {"status": "offline"}
    
    # Check social
    try:
        r = requests.get(f"http://localhost:{_API_PORT}/social/posts", timeout=5)
        if r.status_code == 200:
            status["components"]["social"] = {"status": "online"}
    except:
        status["components"]["social"] = {"status": "offline"}
    
    # Check Engine API
    try:
        r = requests.get("http://localhost:8100/engine/state", timeout=5)
        if r.status_code == 200:
            data = r.json()
            skill_count = data.get("engine", {}).get("skill_count", 0)
            status["components"]["engine"] = {"status": "online", "skills": skill_count}
            status["jobs"]["engine"] = {"skills": skill_count}
    except:
        status["components"]["engine"] = {"status": "offline"}
    
    # Check skills
    try:
        from orchestration.intent_router import get_intent_router
        router = get_intent_router()
        skill_count = len(router.routes)
        status["components"]["skills"] = {"status": "online", "count": skill_count}
        status["jobs"]["skills"] = {"loaded": skill_count}
    except Exception as e:
        status["components"]["skills"] = {"status": "error", "error": str(e)[:50]}
    
    # Get notifications
    try:
        from api.notifications import _notifications
        unread = [n for n in _notifications if not n.read]
        status["notifications"]["unread"] = len(unread)
        status["notifications"]["recent"] = [
            {"title": n.title, "message": n.message, "category": n.category, "timestamp": n.timestamp}
            for n in _notifications[-5:]
        ]
    except:
        pass
    
    return status


@app.get("/system/backends")
def system_backends() -> Dict:
    """Show which backends are currently active."""
    backends = {
        "distributed_mode": os.environ.get("DISTRIBUTED_MODE", "0"),
        "postgresql": {"available": False},
        "redis": {"available": False},
        "sqlite": {"available": True},
        "state_manager": {"backend": "file"},
    }
    try:
        from tools.postgres import get_pg_pool
        pg = get_pg_pool()
        backends["postgresql"] = {"available": pg.available}
        if pg.available:
            backends["state_manager"]["backend"] = "postgresql"
    except Exception:
        pass
    try:
        from tools.redis_client import get_redis
        r = get_redis()
        backends["redis"] = {"available": r.available}
    except Exception:
        pass
    return backends


# ── Metrics (Phase 2 — Speed Engine) ─────────────────────────────
@app.get("/metrics")
def metrics_dump() -> Dict:
    """Full runtime metrics snapshot — latency, error rates, cache, SQLite."""
    return get_metrics().snapshot()


@app.get("/dashboard/performance")
@cached_endpoint(ttl=10)
def dashboard_performance() -> Dict:
    """Performance summary for dashboard UI — top slow endpoints, error rates."""
    metrics = get_metrics().snapshot()
    routes = metrics.get("routes", {})
    sorted_by_latency = sorted(
        routes.items(),
        key=lambda kv: kv[1].get("latency_ms", {}).get("p95", 0),
        reverse=True,
    )
    return {
        "uptime": metrics.get("uptime_str", ""),
        "total_requests": metrics.get("total_requests", 0),
        "total_errors": metrics.get("total_errors", 0),
        "cache": metrics.get("cache", {}),
        "sqlite": metrics.get("sqlite", {}),
        "slowest_endpoints": [
            {"route": r, **s}
            for r, s in sorted_by_latency[:10]
        ],
        "error_prone_endpoints": [
            {"route": r, "error_rate": s.get("error_rate_5m", 0)}
            for r, s in sorted(routes.items(), key=lambda kv: -kv[1].get("error_rate_5m", 0))
            if s.get("error_rate_5m", 0) > 0
        ],
    }


# ── Runtime Healer Status (Phase 3 — Production Ready) ─────────────
@app.get("/healer/status")
def healer_status() -> Dict:
    """Runtime Healer v2 status — circuits, daemons, learned constraints."""
    try:
        from orchestration.runtime_healer import runtime_healer
        snapshot = runtime_healer.health_snapshot()
        return {
            "status": snapshot,
            "learned_constraints": runtime_healer.get_learned_constraints()[-50:],
        }
    except Exception as e:
        return {"error": str(e)}


# ── Confidence Router Status (Phase 3 — Production Ready) ─────────
@app.get("/confidence/status")
def confidence_status() -> Dict:
    """Hybrid confidence stacking status — routes, weights, fallback rates."""
    try:
        if hasattr(agent, "confidence_router") and agent.confidence_router:
            return agent.confidence_router.status_summary()
        return {"error": "confidence_router not initialized"}
    except Exception as e:
        return {"error": str(e)}


# ── Session Replay (Phase 4 — Intelligence Upgrade) ─────────────────
@app.get("/replay/list")
def replay_list(limit: int = 20) -> Dict:
    """List sessions with replay data available."""
    try:
        from orchestration.session_replay import get_replay_engine
        sessions = get_replay_engine().list_sessions(limit)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        return {"error": str(e), "sessions": []}


@app.get("/replay/{session_id}")
def replay_session(session_id: str) -> Dict:
    """Full replay data for a session — capture + describe."""
    try:
        from orchestration.session_replay import get_replay_engine
        engine = get_replay_engine()
        session = engine.capture_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}
        description = engine.describe(session)
        node_data = list(engine.replay(session_id, step=False))
        return {"session_id": session_id, "description": description, "nodes": node_data}
    except Exception as e:
        return {"error": str(e)}


@app.get("/replay/{session_id}/nodes")
def replay_nodes(session_id: str) -> Dict:
    """Node list for a session."""
    try:
        from orchestration.session_replay import get_replay_engine
        engine = get_replay_engine()
        session = engine.capture_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}
        return {
            "session_id": session_id,
            "nodes": [
                {
                    "node_name": n.node_name,
                    "timestamp": n.timestamp,
                    "state": n.state_snapshot,
                }
                for n in session.nodes
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/replay/{session_id}/deltas")
def replay_deltas(session_id: str) -> Dict:
    """Node-to-node deltas for a session."""
    try:
        from orchestration.session_replay import get_replay_engine
        engine = get_replay_engine()
        session = engine.capture_session(session_id)
        if not session:
            return {"error": f"Session not found: {session_id}"}
        return {
            "session_id": session_id,
            "deltas": [
                {"node": n.node_name, "timestamp": n.timestamp, "delta": n.delta_from_previous}
                for n in session.nodes
            ],
        }
    except Exception as e:
        return {"error": str(e)}


# ── Settings Keys (persist from UI to .env) ────────────────────────
class SettingsKeysRequest(BaseModel):
    anthropic: str = ""
    openai: str = ""
    deepseek: str = ""
    openrouter: str = ""
    gemini: str = ""


@app.post("/settings/keys")
def save_settings_keys(req: SettingsKeysRequest) -> Dict:
    from config import persist_setting
    saved = []
    # Skip masked placeholder values
    is_masked = lambda v: v in ("••••••••", "********", "")
    if not is_masked(req.anthropic):
        persist_setting("ANTHROPIC_API_KEY", req.anthropic)
        saved.append("anthropic")
    if not is_masked(req.openai):
        persist_setting("OPENAI_API_KEY", req.openai)
        saved.append("openai")
    if not is_masked(req.deepseek):
        persist_setting("DEEPSEEK_API_KEY", req.deepseek)
        saved.append("deepseek")
    if not is_masked(req.openrouter):
        persist_setting("OPENROUTER_API_KEY", req.openrouter)
        saved.append("openrouter")
    if not is_masked(req.gemini):
        persist_setting("GEMINI_API_KEY", req.gemini)
        saved.append("gemini")
    return {"saved": saved, "count": len(saved)}


@app.post("/betting/place")
def betting_place(req: Dict) -> Dict:
    """Place a bet (simulated or via Playwright) using the DCA engine."""

    player = req.get("player", "")
    market = req.get("market", "")
    line = req.get("line", "")
    query = f"Place a bet on {player} for {market} at line {line} on PrizePicks."
    result = agent.handle(query)
    return {"status": "processing", "query": query, "result": result}


@app.get("/trading/balance")
def trading_balance() -> Dict:
    """Return mock wallet balances for UI."""
    btc_price = 62000.00
    eth_price = 3200.00
    sol_price = 180.00
    btc_amount = 0.12
    eth_amount = 2.5
    sol_amount = 45.0
    return {
        "balance_usd": round(btc_amount * btc_price + eth_amount * eth_price + sol_amount * sol_price, 2),
        "assets": [
            {"symbol": "BTC", "amount": btc_amount, "value_usd": round(btc_amount * btc_price, 2)},
            {"symbol": "ETH", "amount": eth_amount, "value_usd": round(eth_amount * eth_price, 2)},
            {"symbol": "SOL", "amount": sol_amount, "value_usd": round(sol_amount * sol_price, 2)},
        ],
        "status": "ok"
    }


@app.post("/trading/execute")
def trading_execute(req: Dict) -> Dict:
    """Execute a mock trade."""
    symbol = req.get("symbol", "")
    side = req.get("side", "BUY")
    amount = req.get("amount", 0)
    query = f"Execute {side} of {amount} {symbol} on Coinbase."
    result = agent.handle(query)
    return {"status": "executed", "order_id": "CB-99218-X", "query": query, "result": result}


@app.get("/trading/price")
@cached_endpoint(ttl=10)
def trading_price(symbol: str = "BTC-USD") -> Dict:
    """Fetch price from Yahoo Finance or return mock."""
    from features.finance_modules import get_trading
    price = get_trading().fetch_price(symbol)
    if not price:
        price = 64200.50 if "BTC" in symbol else 3450.25 if "ETH" in symbol else 145.20
    return {"symbol": symbol, "price": price, "status": "ok"}


# REMOVED — /skills/list was duplicate, merged into GET /skills above

# ── Media ──────────────────────────────────────────────────────────
class MediaGenRequest(BaseModel):
    prompt: str
    type: str = "image"  # image, video, podcast
    aspect_ratio: str = "1:1"

@app.post("/media/generate")
def media_generate(req: MediaGenRequest) -> Dict:
    query = f"generate a {req.type} with prompt: {req.prompt}"
    result = agent.handle(query)
    return {"status": "processing", "query": query, "result": result}

@app.get("/media/library")
def media_library() -> Dict:
    base = "exports"
    if not os.path.exists(base):
        return {"files": []}
    files = []
    for f in os.listdir(base):
        if f.endswith((".png", ".jpg", ".mp4", ".mp3", ".webp")):
            files.append({
                "name": f,
                "url": f"/media/serve/{f}",
                "type": "video" if f.endswith(".mp4") else "audio" if f.endswith(".mp3") else "image",
                "size": os.path.getsize(os.path.join(base, f)),
                "mtime": os.path.getmtime(os.path.join(base, f))
            })
    return {"files": sorted(files, key=lambda x: x["mtime"], reverse=True)}


@app.get("/systems/registry")
def systems_registry() -> Dict:
    from features.agent_registry import get_agent_registry
    return {"agents": get_agent_registry().get_all()}

@app.get("/systems/health")
def systems_health() -> Dict:
    from features.systems_bridge import get_systems_bridge
    from features.status_tracker import get_status_tracker
    bridge = get_systems_bridge()
    tracker = get_status_tracker()
    
    health = {
        "superalgos": bridge.check_superalgos(),
        "benchmarks": bridge.get_benchmark_summary(),
        "content_engine": {"status": tracker.get_system_status("content_engine")},
        "betting_pipeline": {"status": tracker.get_system_status("betting_pipeline")},
        "blackmind": {"status": tracker.get_agent_status("blackmind"), "capabilities": ["experimentation", "paper_generation"]}
    }
    return health

@app.post("/systems/content/trigger")
def systems_content_trigger(req: Dict) -> Dict:
    from features.systems_bridge import get_systems_bridge
    bridge = get_systems_bridge()
    return bridge.run_content_pipeline(req.get("topic", "AI Trends"), req.get("format", "podcast"))

@app.post("/lab/experiment")
def lab_experiment(req: Dict) -> Dict:
    from features.blackmind_lab import get_blackmind_lab
    lab = get_blackmind_lab()
    return lab.run_experiment(req.get("id"), req.get("hypothesis"), req.get("dataset_id"))

@app.post("/lab/paper")
def lab_paper(req: Dict) -> Dict:
    from features.blackmind_lab import get_blackmind_lab
    lab = get_blackmind_lab()
    return lab.generate_science_paper(req.get("experiment_id"))

# ── Intelligence ───────────────────────────────────────────────────
@app.get("/news/unified")
def news_unified() -> Dict:
    from features.finance_modules import get_news
    from features.opportunity_scout import get_scout
    from brain.soul import get_soul
    
    items = get_news().fetch_all()
    
    # Autonomous Opportunity Scout Trigger
    soul = get_soul()
    get_scout().scout([i.to_dict() for i in items], soul.goals)

    # Categorize items
    categorized = {"tech": [], "finance": [], "ai": [], "general": []}
    for item in items:
        text = (item.title + " " + item.summary).lower()
        if any(w in text for w in ["ai", "llm", "gpt", "model"]): categorized["ai"].append(item.to_dict())
        elif any(w in text for w in ["crypto", "stock", "market", "price"]): categorized["finance"].append(item.to_dict())
        elif any(w in text for w in ["apple", "google", "meta", "nvidia", "tech"]): categorized["tech"].append(item.to_dict())
        else: categorized["general"].append(item.to_dict())
    return {"categories": categorized, "total": len(items)}

@app.get("/opportunities")
def list_opportunities() -> Dict:
    from features.opportunity_scout import get_scout
    return {"opportunities": get_scout().get_latest()}

@app.post("/knowledge/synthesize")
def synthesize_knowledge(tag: str) -> Dict:
    from knowledge.bank import get_knowledge_bank
    from features.synthesis_engine import get_synthesis_engine
    
    bank = get_knowledge_bank()
    fragments = bank.fragments_by_tag(tag)
    if not fragments:
        return {"error": f"No fragments found for tag '{tag}'"}
        
    engine = get_synthesis_engine()
    result = engine.synthesize(tag, [f.__dict__ for f in fragments])
    return result


@app.post("/news/summarize")
def news_summarize(req: Dict) -> Dict:
    """Summarize a news item using the LLM."""
    title = req.get("title", "")
    url = req.get("url", "")
    query = f"summarize this news article: {title} at {url}"
    result = agent.handle(query)
    return {"summary": result.get("output", "Summary generation failed."), "status": "ok"}


@app.post("/news/action")
def news_action(req: Dict) -> Dict:
    """Trigger a business action (e.g., create social post) from news."""
    action = req.get("action", "research")
    title = req.get("title", "")
    query = f"Action: {action} based on news: {title}"
    result = agent.handle(query)
    return {"result": result.get("output", "Action failed."), "status": "ok"}


# ── Uploads ────────────────────────────────────────────────────────
class AgentUploadRequest(BaseModel):
    name: str
    content: str

@app.post("/upload/agent")
def upload_agent(req: AgentUploadRequest) -> Dict:
    """Upload a skill/agent file. Validated for safety against traversal and malicious code."""
    name = req.name
    content = req.content

    if not name or ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid agent name")

    safe_name = os.path.basename(name)
    if not safe_name:
        raise HTTPException(status_code=400, detail="Invalid agent name")

    if not safe_name.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files allowed")

    if len(content) > 200 * 1024:
        raise HTTPException(status_code=400, detail="Content too large (max 200KB)")

    # Reject known-dangerous patterns
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(content):
            raise HTTPException(status_code=400, detail=f"Blocked dangerous pattern: {pattern.pattern}")

    upload_dir = os.path.join("skills", "_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    path = os.path.join(upload_dir, safe_name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "ok", "path": path, "message": "Agent uploaded"}

@app.post("/upload/folder")
def upload_folder_context(name: str, description: str = "") -> Dict:
    """Simulate a folder ingestion into the knowledge bank."""
    return {"status": "ok", "ingested": name, "message": "Folder metadata registered for background research"}


# ── Governor API ────────────────────────────────────────────────────
_governor_state = {
    "mode": "checkpoint",
    "queue": [],
    "history": [],
}

_GOVERNOR_ROUTES = [
    {"patterns": ["code", "function", "class", "component", "api", "build", "deploy", "refactor"], "target": "openhub", "action": "pipeline"},
    {"patterns": ["strategy", "budget", "revenue", "market", "marketing", "campaign", "finance"], "target": "uplift-venture", "action": "business_module"},
    {"patterns": ["community", "member", "course", "marketplace", "education"], "target": "ul2", "action": "community_feature"},
    {"patterns": ["call", "voice", "routing", "recording", "sip", "telephony"], "target": "aetherdesk", "action": "call_center"},
    {"patterns": ["research", "simulation", "clinical", "archetype", "playbook", "bio", "genome"], "target": "bb-tech", "action": "research_experiment"},
]

class GovernorRouteRequest(BaseModel):
    task: str
    context: Optional[Dict[str, Any]] = None

class GovernorActionRequest(BaseModel):
    escalation_id: str
    reason: Optional[str] = None

class GovernorModeRequest(BaseModel):
    mode: str

@app.post("/governor/route")
def governor_route(req: GovernorRouteRequest) -> Dict:
    task_lower = req.task.lower()
    context = req.context or {}

    best_match = {"target": "uplift-venture", "action": "general", "score": 0}
    for route in _GOVERNOR_ROUTES:
        score = sum(1 for p in route["patterns"] if p in task_lower)
        if score > best_match["score"]:
            best_match = {**route, "score": score}

    confidence = min(0.95, 0.5 + best_match["score"] * 0.1)
    amount = context.get("amount", 0)
    requires_oversight = confidence < 0.7 or amount > 500

    decision = {
        "target_system": best_match["target"],
        "action": best_match["action"],
        "confidence": round(confidence, 2),
        "requires_oversight": requires_oversight,
        "oversight_mode": _governor_state["mode"] if requires_oversight else "none",
    }

    if requires_oversight and _governor_state["mode"] == "checkpoint":
        esc_id = f"ESC-{int(time.time())}-{best_match['target'][:3]}"
        _governor_state["queue"].append({
            "id": esc_id,
            "task": req.task,
            "decision": decision,
            "context": context,
            "created_at": datetime.now().isoformat(),
        })
        return {"status": "awaiting_oversight", "escalation_id": esc_id, "decision": decision}

    return {"status": "routed", "decision": decision}

@app.post("/governor/approve")
def governor_approve(req: GovernorActionRequest) -> Dict:
    idx = next((i for i, q in enumerate(_governor_state["queue"]) if q["id"] == req.escalation_id), -1)
    if idx == -1:
        raise HTTPException(status_code=404, detail="Escalation not found")
    item = _governor_state["queue"].pop(idx)
    _governor_state["history"].append({**item, "status": "approved", "resolved_at": datetime.now().isoformat()})
    if len(_governor_state["history"]) > 1000:
        _governor_state["history"] = _governor_state["history"][-1000:]
    return {"status": "approved", "decision": item["decision"]}

@app.post("/governor/reject")
def governor_reject(req: GovernorActionRequest) -> Dict:
    idx = next((i for i, q in enumerate(_governor_state["queue"]) if q["id"] == req.escalation_id), -1)
    if idx == -1:
        raise HTTPException(status_code=404, detail="Escalation not found")
    item = _governor_state["queue"].pop(idx)
    _governor_state["history"].append({**item, "status": "rejected", "reason": req.reason, "resolved_at": datetime.now().isoformat()})
    if len(_governor_state["history"]) > 1000:
        _governor_state["history"] = _governor_state["history"][-1000:]
    return {"status": "rejected"}

@app.get("/governor/status")
def governor_status() -> Dict:
    return {
        "mode": _governor_state["mode"],
        "pending": len(_governor_state["queue"]),
        "queue": _governor_state["queue"][-20:],
        "history": _governor_state["history"][-20:],
    }

@app.post("/governor/mode")
def governor_mode(req: GovernorModeRequest) -> Dict:
    if req.mode not in ("shadow", "checkpoint", "recovery"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be shadow, checkpoint, or recovery")
    _governor_state["mode"] = req.mode
    return {"status": "updated", "mode": req.mode}


# ── Autonomy Enhanced ─────────────────────────────────────────────
@app.get("/autonomy/ceo")
def autonomy_ceo_status() -> Dict:
    from features.autonomy import get_autonomy
    status = get_autonomy().get_status()
    # Add fake 'live trace' for UI demo if no real logs yet
    if not status.get("dream_stats", {}).get("last_cycle"):
        status["live_trace"] = [
            {"time": "09:21:04", "msg": "Analyzing 'Aether OS' market potential..."},
            {"time": "09:21:15", "msg": "Gathered 14 competitor fragments from HackerNews."},
            {"time": "09:22:01", "msg": "Generating SaaS architecture proposal..."},
            {"time": "09:22:30", "msg": "Self-correcting build constraints (Node.js version mismatch)."},
        ]
    return status


# ── UI ─────────────────────────────────────────────────────────────
# ── UI & SPA Catch-All ─────────────────────────────────────────────
@app.get("/")
async def serve_root():
    path = "aether-dashboard/dist/index.html"
    if os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("<h1>Aether Dashboard Not Found</h1><p>Run 'npm run build' in aether-dashboard first.</p>")

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # Never intercept API docs or internal routes
    if full_path in ("docs", "openapi.json", "redoc"):
        raise HTTPException(status_code=404, detail="Not Found")
    # If the path looks like a file (has an extension), try to serve it from dist
    # Otherwise, return index.html for SPA routing
    base = os.path.abspath("aether-dashboard/dist")
    dist_path = os.path.abspath(os.path.join(base, full_path))
    if not dist_path.startswith(base):
        raise HTTPException(status_code=403, detail="path traversal blocked")
    if os.path.isfile(dist_path):
        return FileResponse(dist_path)
    
    # Fallback to index.html for SPA
    index_path = "aether-dashboard/dist/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    
    # Allow API routes to bubble up (though FastAPI usually handles this via order)
    raise HTTPException(status_code=404, detail="Not Found")

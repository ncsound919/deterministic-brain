"""FastAPI server v2.5 — /task /reason /bundle /skills /forge /dashboard /relay /health"""
from __future__ import annotations
import json
import os
import traceback
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from orchestration.event_bus import event_bus
from brain.autodream import run_autodream, consolidate_knowledge_bank
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay
from api.middleware import RequestLoggingMiddleware, get_route_stats

# Route modules
from api.routes.settings import router as settings_router
from api.routes.voice import router as voice_router
from api.routes.devpets import router as devpets_router
from api.routes.kairos import router as kairos_router
from api.routes.evolution import router as evolution_router

app   = FastAPI(title="Deterministic Brain", version="2.5.0")
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()
forge = Forge()
dash  = Dashboard()

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
        bank.rebuild_index()
    except Exception:
        pass

_seed_knowledge()

# Middleware
app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(settings_router)
app.include_router(voice_router)
app.include_router(devpets_router)
app.include_router(kairos_router)
app.include_router(evolution_router)


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


class KnowledgeIngestRequest(BaseModel):
    url: str
    tags: List[str] = []


class KnowledgeTextIngestRequest(BaseModel):
    text: str
    title: str
    tags: List[str] = []


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SnippetSaveRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []


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


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    try:
        result = agent.handle(req.query)
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
    return {"query": req.query, "task": task, "decision": decision.to_dict()}


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)


@app.get("/skills")
def list_skills() -> Dict:
    return {"skills": forge.list_skills()}


# ── Bundles (Gap 7: schema validation) ─────────────────────────────
@app.get("/bundles")
def list_bundles() -> Dict[str, List[Dict]]:
    import yaml
    config_path = os.environ.get("SWARM_CONFIG", "swarm.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}
    bundles = []
    for name, data in config.get("bundles", {}).items():
        try:
            bd = BundleDefinition(**data)
            bundles.append({"name": name, "description": bd.description, "lanes": bd.lanes})
        except Exception:
            continue  # skip malformed bundle entries
    return {"bundles": bundles}


# ── Skill Chains (Gap fix: chains were never wired) ─────────────────
@app.get("/chains")
def list_chains() -> Dict:
    try:
        from features.skill_chains_loader import get_chain_status
        return get_chain_status()
    except Exception as e:
        return {"error": str(e)}


@app.get("/chains/{chain_name}")
def get_chain(chain_name: str) -> Dict:
    try:
        from features.skill_chains_loader import get_chain_status
        return get_chain_status(chain_name)
    except Exception as e:
        return {"error": str(e)}


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
def feed() -> Dict:
    return {"events": dash.recent_events(50)}


@app.get("/dashboard/audit")
def audit() -> Dict:
    return {"events": dash.audit_feed()}


@app.get("/dashboard/stats")
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
def autodream_status() -> Dict:
    path = ".autodream_last_run.json"
    if os.path.exists(path):
        return json.loads(open(path).read())
    return {"status": "never_run"}


# ── Knowledge Bank ─────────────────────────────────────────────────
@app.get("/knowledge/stats")
def knowledge_stats() -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        return bank.stats()
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/ingest")
def knowledge_ingest(req: KnowledgeIngestRequest) -> Dict:
    try:
        from knowledge.ingester import get_ingester
        from knowledge.bank import get_knowledge_bank
        ingester = get_ingester()
        bank = get_knowledge_bank()
        fragments = ingester.ingest_url(req.url, req.tags)
        count = bank.add_fragments(fragments)
        return {"status": "ok", "ingested": count, "url": req.url, "tags": req.tags}
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/ingest-text")
def knowledge_ingest_text(req: KnowledgeTextIngestRequest) -> Dict:
    try:
        from knowledge.ingester import get_ingester
        from knowledge.bank import get_knowledge_bank
        ingester = get_ingester()
        bank = get_knowledge_bank()
        fragments = ingester.ingest_text(req.text, req.title, req.tags)
        count = bank.add_fragments(fragments)
        return {"status": "ok", "ingested": count, "title": req.title, "tags": req.tags}
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/search")
def knowledge_search(req: KnowledgeSearchRequest) -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        results = bank.query(req.query, top_k=req.top_k)
        return {
            "query": req.query,
            "results": [
                {
                    "id": f.id,
                    "source_type": f.source_type,
                    "source_url": f.source_url,
                    "source_title": f.source_title,
                    "chunk_text": f.chunk_text[:500],
                    "tags": f.tags,
                    "confidence": f.confidence,
                    "access_count": f.access_count,
                    "score": round(score, 4),
                }
                for f, score in results
            ],
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/knowledge/fragments")
def knowledge_fragments(source_type: str = "") -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        if source_type:
            frags = bank.fragments_by_source(source_type)
        else:
            frags = bank.all_fragments()
        return {
            "fragments": [f.to_dict() for f in frags],
            "count": len(frags),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/knowledge/snippets")
def knowledge_snippets() -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        return {"snippets": bank.list_snippets()}
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/snippets")
def knowledge_save_snippet(req: SnippetSaveRequest) -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        snippet = bank.save_snippet(req.title, req.content, req.tags)
        return {"status": "ok", "snippet": snippet}
    except Exception as e:
        return {"error": str(e)}


@app.delete("/knowledge/snippets/{snippet_id}")
def knowledge_delete_snippet(snippet_id: str) -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        bank.delete_snippet(snippet_id)
        return {"status": "ok", "deleted": snippet_id}
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/generate-refs")
def knowledge_generate_refs() -> Dict:
    try:
        from knowledge.bank import get_knowledge_bank
        bank = get_knowledge_bank()
        clusters = bank.cluster_by_tags(min_size=5)
        generated = []
        for tag, frags in clusters.items():
            path = bank.generate_ref_doc(tag, frags)
            generated.append({"tag": tag, "fragments": len(frags), "path": path})
        return {"status": "ok", "generated": len(generated), "refs": generated}
    except Exception as e:
        return {"error": str(e)}


@app.post("/knowledge/consolidate")
def knowledge_consolidate(dry_run: bool = True) -> Dict:
    return consolidate_knowledge_bank(dry_run=dry_run)


# ── Soul ───────────────────────────────────────────────────────────
@app.get("/soul")
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
            s.goals = req.agenda["goals"] or s.goals
        if "anti_goals" in req.agenda:
            s.anti_goals = req.agenda["anti_goals"] or s.anti_goals
        if "autonomous_directives" in req.agenda:
            s.autonomous_directives = req.agenda["autonomous_directives"] or s.autonomous_directives
    if req.context:
        ctx = req.context
        if "expertise" in ctx:
            s.expertise = ctx["expertise"] or s.expertise
        if "learning" in ctx:
            s.learning = ctx["learning"] or s.learning
        if "notes" in ctx:
            s.notes = ctx.get("notes", s.notes)
        if "stack" in ctx:
            stack = ctx["stack"]
            if "languages" in stack:
                s.stack_languages = stack["languages"] or s.stack_languages
            if "frameworks" in stack:
                s.stack_frameworks = stack["frameworks"] or s.stack_frameworks
            if "tools" in stack:
                s.stack_tools = stack["tools"] or s.stack_tools
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
    path = os.path.join("ui", filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path)


@app.get("/preview/{build_id}/{filename:path}")
def serve_build_file(build_id: str, filename: str) -> FileResponse:
    path = os.path.join("builds", build_id, filename)
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
def llm_status() -> Dict:
    has_openrouter = bool(os.getenv("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    enabled = os.getenv("LLM_ENABLED", "").lower() == "true" or has_openrouter or has_anthropic
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
            "social": {"available": True, "label": "Social Media Scheduler"},
            "saas_builder": {"available": True, "label": "SaaS Builder"},
            "skill_expander": {"available": True, "label": "Auto Skill Expansion"},
            "betting": {"available": True, "label": "Sports Betting Engine"},
            "trading": {"available": True, "label": "Trading Engine"},
            "news": {"available": True, "label": "News Feed (HN + Dev.to)"},
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
def news_feed() -> Dict:
    from features.finance_modules import get_news
    items = get_news().fetch_all()
    return {"items": [i.to_dict() for i in items], "count": len(items)}


@app.get("/odds")
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


@app.get("/trading/price")
def trading_price(symbol: str = "AAPL") -> Dict:
    from features.finance_modules import get_trading
    price = get_trading().fetch_price(symbol)
    return {"symbol": symbol, "price": price}


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


@app.get("/trading/balance")
def trading_balance() -> Dict:
    return {"balance": 0, "note": "stub — connect Cash App / Stripe in settings"}


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


# ── Health ─────────────────────────────────────────────────────────
@app.get("/health")
def health() -> Dict:
    return dash.health()


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
    if req.anthropic:
        persist_setting("ANTHROPIC_API_KEY", req.anthropic)
        saved.append("anthropic")
    if req.openai:
        persist_setting("OPENAI_API_KEY", req.openai)
        saved.append("openai")
    if req.deepseek:
        persist_setting("DEEPSEEK_API_KEY", req.deepseek)
        saved.append("deepseek")
    if req.openrouter:
        persist_setting("OPENROUTER_API_KEY", req.openrouter)
        saved.append("openrouter")
    if req.gemini:
        persist_setting("GEMINI_API_KEY", req.gemini)
        saved.append("gemini")
    return {"saved": saved, "count": len(saved)}


# ── UI ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("ui/index.html")


@app.get("/ui")
def serve_ui_redirect() -> FileResponse:
    return FileResponse("ui/index.html")

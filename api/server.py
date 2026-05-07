"""FastAPI server v2.4 — /task /reason /bundle /skills /forge /dashboard /relay /health /devpets"""
from __future__ import annotations
import json
import os
import glob
from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from pathlib import Path

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from orchestration.kairos_daemon import get_daemon, start_kairos, stop_kairos, kairos_status
from orchestration.event_bus import event_bus
from brain.autodream import run_autodream
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay
from api.middleware import RequestLoggingMiddleware, get_route_stats
from api.routes.settings import router as settings_router
import numpy as np
import struct

# Voice mode (lazy-loads STT/TTS models on first use)
_voice_mode = None

def _get_voice():
    global _voice_mode
    if _voice_mode is None:
        from dialogue.voice_mode import VoiceMode
        _voice_mode = VoiceMode(seed=42)
        # Register backend handlers
        _voice_mode.register_backend("run_task",
            lambda text, **kw: agent.handle(text))
        _voice_mode.register_backend("run_bundle",
            lambda text, **kw: swarm.dispatch(
                kw.get("slots", {}).get("bundle", "scaffold-rest-api"),
                kw.get("slots", {})))
    return _voice_mode

app   = FastAPI(title="Deterministic Brain", version="2.4.0")
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()
forge = Forge()
dash  = Dashboard()

# Middleware: CORS + request logging
app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware)
app.include_router(settings_router)

# DevPets directory (Tamagotchi — pets grow here, battle on the website)
DEVPETS_DIR = Path("devpets")
DEVPETS_DIR.mkdir(exist_ok=True)


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

class DevPetGenerateRequest(BaseModel):
    pet_name: str = "DevPet"
    db_path:  str = "traces.db"

class DialogueRequest(BaseModel):
    text: str
    seed: Optional[int] = None


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    """Parse → Reason → Execute. Returns full state including reasoning trace."""
    return agent.handle(req.query)


@app.post("/reason")
def reason_only(req: TaskRequest) -> Dict:
    """
    Run ONLY the reasoning pipeline — no skill execution.
    Returns the full DecisionResult breakdown so the UI can show
    chosen_skill, chosen_config, confidence, pre_audit, and step trace
    before anything is written to disk.
    """
    task = agent.parser.parse(req.query)
    decision = agent.reasoner.decide(
        task             = task,
        skill_candidates = list(agent.skills.keys()),
        scorer_fn        = agent._decision_scorer,
        constraints      = agent._build_constraints(task),
        variable_domains = agent._variable_domains(task),
    )
    return {
        "query":    req.query,
        "task":     task,
        "decision": decision.to_dict(),
    }


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)

@app.get("/skills")
def list_skills() -> Dict:
    return {"skills": forge.list_skills()}


# ── Relay ──────────────────────────────────────────────────────────
@app.post("/relay")
def relay_forward(req: RelayRequest) -> Dict:
    return relay.forward(req.agent, req.path, req.body,
                         req.method, verify_inbound=req.verify)

@app.post("/relay/broadcast")
def relay_broadcast(body: Dict) -> Dict:
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

# ── autoDream ────────────────────────────────────────────────
@app.post("/autodream")
def autodream(req: AutoDreamRequest) -> Dict:
    """Run autoDream. Pass dry_run=true to preview without changes."""
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


# ── Bundles ───────────────────────────────────────────────────
@app.get("/bundles")
def list_bundles() -> Dict[str, List[Dict]]:
    """Return all available bundles from swarm.yaml for the UI dropdown."""
    import yaml
    config_path = os.environ.get("SWARM_CONFIG", "swarm.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}
    bundles = []
    for name, data in config.get("bundles", {}).items():
        bundles.append({
            "name": name,
            "description": data.get("description", ""),
            "lanes": data.get("lanes", []),
        })
    return {"bundles": bundles}


# ── DevPets (Tamagotchi — pets grow here, battle on devpet-web/) ──
@app.get("/devpets")
def list_devpets() -> Dict[str, List[Dict]]:
    """List all DevPets from the devpets/ directory."""
    pets = []
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            identity = data.get("identity", {})
            pets.append({
                "id": identity.get("developer_id", Path(fpath).stem),
                "pet_name": identity.get("pet_name", "Unknown"),
                "species": identity.get("pet_species", "Unknown"),
                "level": data.get("level", 1),
                "evolution_stage": data.get("evolution_stage", 1),
                "pet_type": data.get("pet_type", "normal"),
                "battle_stats": data.get("battle_stats", {}),
                "file": Path(fpath).name,
            })
        except Exception:
            continue
    return {"devpets": pets, "count": len(pets)}


@app.get("/devpets/{pet_id}")
def get_devpet(pet_id: str) -> Dict:
    """Get a single DevPet's full data."""
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            identity = data.get("identity", {})
            if identity.get("developer_id") == pet_id or Path(fpath).stem == pet_id:
                return {"pet": data, "file": Path(fpath).name}
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")


@app.get("/devpets/{pet_id}/stats")
def get_devpet_stats(pet_id: str) -> Dict:
    """Get a DevPet's battle stats and work fingerprint."""
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            if (data.get("identity", {}).get("developer_id") == pet_id
                    or Path(fpath).stem == pet_id):
                return {
                    "pet_name": data.get("identity", {}).get("pet_name"),
                    "level": data.get("level"),
                    "evolution_stage": data.get("evolution_stage"),
                    "pet_type": data.get("pet_type"),
                    "battle_stats": data.get("battle_stats", {}),
                    "work_fingerprint": data.get("work_fingerprint", {}),
                    "tool_branches": {
                        k: {"tier": v.get("tier"), "xp": v.get("xp"),
                            "signature_moves": v.get("signature_moves", [])}
                        for k, v in data.get("tool_branches", {}).items()
                    },
                }
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")


@app.post("/devpets/generate")
def generate_devpet(req: DevPetGenerateRequest) -> Dict:
    """Generate a .devpet file from the trace database (Tamagotchi mode)."""
    from devpet.tracker import DevPetTracker
    from devpet.export import save_devpet_file

    tracker = DevPetTracker(db_path=req.db_path, pet_name=req.pet_name)
    pet = tracker.process_events()
    tracker.close()

    path = DEVPETS_DIR / f"{pet.developer_id}.json"
    save_devpet_file(pet, str(path))

    event_bus.emit("devpet_generated",
        pet_name=pet.pet_name, developer_id=pet.developer_id,
        level=pet.level, evolution_stage=pet.evolution_stage)

    return {
        "pet_name": pet.pet_name,
        "species": pet.species,
        "level": pet.level,
        "evolution_stage": pet.evolution_stage,
        "battle_stats": pet.battle_stats.to_dict(),
        "file": str(path),
    }


@app.post("/devpets/{pet_id}/image")
async def upload_devpet_image(pet_id: str, image: UploadFile = File(...)) -> Dict:
    """Upload card art for a DevPet."""
    # Verify pet exists
    pet_found = False
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        data = json.loads(Path(fpath).read_text())
        if data.get("identity", {}).get("developer_id") == pet_id:
            pet_found = True
            break
    if not pet_found:
        raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")

    img_dir = DEVPETS_DIR / "images"
    img_dir.mkdir(exist_ok=True)
    ext = Path(image.filename or "card.png").suffix or ".png"
    img_path = img_dir / f"{pet_id}{ext}"
    img_path.write_bytes(await image.read())

    return {"status": "ok", "image_path": str(img_path)}


# ── Dialogue ──────────────────────────────────────────────────
@app.post("/dialogue/process")
def dialogue_process(req: DialogueRequest) -> Dict:
    """Process text through the dialogue pipeline (NLU, state machine, response)."""
    from dialogue import create_dialogue_pipeline

    pipeline = create_dialogue_pipeline(seed=req.seed)
    result = pipeline.process(req.text)
    pipeline.close()

    event_bus.emit("dialogue_turn",
        input_text=req.text, intent=result.intent,
        response=result.response, state=result.state)

    return {
        "response": result.response,
        "intent": result.intent,
        "confidence": result.intent_confidence,
        "slots": result.slots,
        "state": result.state,
        "action": result.action,
        "session_id": result.session_id,
    }


# ── Dashboard (middleware stats) ──────────────────────────────
@app.get("/dashboard/middleware-stats")
def middleware_stats_route() -> Dict:
    """Return per-route latency, error rate, and throughput stats."""
    return {"routes": get_route_stats()}


# ── Voice (faster-whisper STT + piper-tts) ──────────────────
@app.get("/voice/status")
def voice_status() -> Dict:
    return {
        "status": "ready",
        "stt": "faster-whisper (tiny.en)",
        "tts": "piper-tts (en_US-lessac-medium)",
        "stream": "ws://localhost:8000/voice/stream",
    }


@app.post("/voice/transcribe")
async def voice_transcribe(body: Dict) -> Dict:
    """Transcribe base64 PCM audio to text using faster-whisper."""
    import base64
    vm = _get_voice()
    raw = body.get("audio", "")
    if not raw:
        return {"text": "", "error": "No audio data"}
    try:
        audio_bytes = base64.b64decode(raw)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        text = vm.transcriber.transcribe(audio_np, sample_rate=16000)
        return {"text": text, "confidence": 0.9 if text else 0.0}
    except Exception as e:
        return {"text": "", "error": str(e)}


@app.post("/voice/speak")
async def voice_speak(body: Dict) -> bytes:
    """Synthesize text to WAV audio using piper-tts."""
    from fastapi.responses import Response
    vm = _get_voice()
    text = body.get("text", "")
    if not text:
        return Response(content=vm.synthesizer.synthesize("No text provided."),
                        media_type="audio/wav")
    audio = vm.synthesizer.synthesize(text)
    return Response(content=audio, media_type="audio/wav")


@app.websocket("/voice/stream")
async def voice_stream(websocket):
    """Real-time voice streaming — mic → STT → pipeline → TTS → speaker."""
    from fastapi import WebSocket
    await websocket.accept()
    vm = _get_voice()
    vm.reset()

    try:
        while True:
            # Receive binary audio chunk (PCM 16-bit, 16kHz, mono)
            data = await websocket.receive()
            if data["type"] == "websocket.disconnect":
                break

            if "bytes" in data:
                audio_bytes = data["bytes"]
                audio_np = (np.frombuffer(audio_bytes, dtype=np.int16)
                             .astype(np.float32) / 32768.0)
                text = vm.add_audio_chunk(audio_np)

                if text:
                    # Process through dialogue pipeline
                    result = vm.process(text)

                    # Send transcription + dialogue back
                    await websocket.send_json({
                        "type": "transcription",
                        "text": text,
                        "dialogue": result.get("dialogue", {}),
                    })

                    # Synthesize and send audio response
                    audio_wav = vm.synthesizer.synthesize(result["response"])
                    await websocket.send_bytes(audio_wav)
    except Exception:
        pass
    finally:
        vm.close()


# ── KAIROS ───────────────────────────────────────────────────
@app.post("/kairos/start")
def kairos_start() -> Dict:
    return start_kairos()

@app.post("/kairos/stop")
def kairos_stop() -> Dict:
    return stop_kairos()

@app.get("/kairos/status")
def kairos_status_endpoint() -> Dict:
    return kairos_status()

@app.get("/kairos/today")
def kairos_today() -> Dict:
    from features.kairos import get_today
    return get_today()

@app.get("/kairos/{date}")
def kairos_date(date: str) -> Dict:
    from features.kairos import get_date
    return get_date(date)

@app.get("/kairos/stats")
def kairos_stats() -> Dict:
    from features.kairos import get_stats
    return get_stats()

@app.get("/health")
def health() -> Dict:
    return dash.health()


# ── Health Monitor ─────────────────────────────────────────────
@app.get("/health/monitor")
def health_monitor() -> Dict:
    """Aggregated health status: daemon, circuit breakers, evolution, error rate."""
    try:
        from orchestration.runtime_healer import runtime_healer
        circuits = runtime_healer.all_circuit_states()
        heals = runtime_healer.recent_heals(10)
    except ImportError:
        circuits = []
        heals = []

    try:
        from evolution.skill_evolver import SkillEvolver
        evolver = SkillEvolver()
        skills = evolver.all_stats()
    except ImportError:
        skills = []

    total_runs = sum(s.get("runs", 0) for s in skills)
    total_successes = sum(s["runs"] * s.get("success_rate", 0) for s in skills)
    error_rate = round(1 - (total_successes / max(total_runs, 1)), 4)

    return {
        "daemon": kairos_status(),
        "circuit_breakers": circuits,
        "recent_heals": heals,
        "skills_health": skills[:10],
        "error_rate": error_rate,
        "total_skills_tracked": len(skills),
        "last_evolve": max((s.get("last_run_ts", 0) for s in skills), default=0),
    }


@app.get("/health/heals")
def health_heals(limit: int = 20) -> Dict:
    """Recent heal events."""
    try:
        from orchestration.runtime_healer import runtime_healer
        return {"heals": runtime_healer.recent_heals(limit)}
    except ImportError:
        return {"heals": []}


@app.get("/health/skills")
def health_skills() -> Dict:
    """Per-skill health from evolver + circuit breaker states."""
    try:
        from evolution.skill_evolver import SkillEvolver
        evolver = SkillEvolver()
        return {"skills": evolver.all_stats()}
    except ImportError:
        return {"skills": []}


# ── Evolution ──────────────────────────────────────────────────
@app.post("/evolution/nightly-score")
def nightly_score() -> Dict:
    """Run daily skill scoring and evolution (triggers weight updates)."""
    try:
        from evolution import NightlyScorer
        scorer = NightlyScorer()
        report = scorer.run_daily_score()
        event_bus.emit("evolution_ran", evolved_skills=report["evolved_skills"])
        return report
    except ImportError as e:
        raise HTTPException(status_code=501, detail=f"Evolution module: {e}")


@app.get("/evolution/report")
def evolution_report() -> Dict:
    """Get last nightly score report (does not re-run)."""
    try:
        from evolution import NightlyScorer
        scorer = NightlyScorer()
        return scorer.generate_report()
    except ImportError:
        return {"status": "module_not_available"}


# ── UI ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("ui/index.html")

"""Settings API — read, update, export, and schema for brain configuration."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import cfg, reload_config, get_setting_schema, persist_setting

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingUpdate(BaseModel):
    key: str
    value: str


@router.get("")
async def get_settings():
    """Return all current configuration values."""
    return {
        "config": cfg.summary(),
        "runtime": {
            "tracing_enabled": cfg.tracing_enabled,
            "kairos_enabled": cfg.kairos_enabled,
            "autodream_enabled": cfg.autodream_enabled,
        },
    }


@router.get("/schema")
async def settings_schema():
    """Return typed schema for UI form generation."""
    return {"groups": get_setting_schema()}


@router.post("/update")
async def update_setting(update: SettingUpdate):
    """Persist a single setting and reload configuration."""
    key = update.key.upper()
    try:
        persist_setting(key, update.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    new_cfg = reload_config()
    return {
        "status": "updated",
        "key": key,
        "value": update.value,
        "message": f"Setting {key} updated. Server restart required for some changes.",
    }


@router.get("/export")
async def export_settings():
    """Download current settings (API keys redacted for security)."""
    import os
    env_path = os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(env_path):
        raise HTTPException(status_code=404, detail="No .env file found")

    # Read and redact sensitive values
    sensitive_keys = {
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
        "GEMINI_API_KEY", "QDRANT_API_KEY", "NEO4J_PASSWORD", "STRIPE_SECRET_KEY",
        "DISCORD_BOT_TOKEN", "GITHUB_TOKEN", "REDDIT_CLIENT_SECRET", "ODDS_API_KEY",
        "TAVILY_API_KEY", "ELEVENLABS_API_KEY", "KLING_API_KEY", "WHISPER_API_KEY",
    }

    lines = []
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                if key.upper() in sensitive_keys:
                    lines.append(f"{key}=***REDACTED***")
                else:
                    lines.append(line)

    content = "\n".join(lines)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content, media_type="text/plain",
                             headers={"Content-Disposition": "attachment; filename=brain-settings.env"})

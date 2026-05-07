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
    """Download current .env file content."""
    import os
    env_path = os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(env_path):
        raise HTTPException(status_code=404, detail="No .env file found")
    content = open(env_path).read()
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content, media_type="text/plain",
                             headers={"Content-Disposition": "attachment; filename=.env"})

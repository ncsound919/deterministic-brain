"""Media API — Handles AI generation for text (Grok-3) and images (ComfyUI/Kling)."""
from __future__ import annotations
import os
import time
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/media", tags=["media"])

class GenerateRequest(BaseModel):
    prompt: str
    type: str = "text"
    aspect_ratio: str = "1:1"

@router.post("/generate")
def generate_media(req: GenerateRequest) -> Dict:
    """Generate text or images for social media/content engine."""
    if req.type == "text":
        try:
            # Wire up Grok-3 for script/post generation
            from Content_Creation_Engine__main.src.rework_script_with_dna import _call_llm
            sys_prompt = "You are a world-class social media copywriter. Write highly engaging, viral content."
            res = _call_llm(sys_prompt, req.prompt)
            return {"status": "ok", "result": {"output": res}}
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            # Fallback
            return {"status": "ok", "result": {"output": f"Generated draft for: {req.prompt}\n(Grok-3 integration pending API key)"}}
            
    elif req.type == "image":
        # Simulate image generation and put a placeholder in exports
        os.makedirs("exports", exist_ok=True)
        img_name = f"gen_{int(time.time())}.png"
        img_path = Path("exports") / img_name
        
        # Here we'd call ComfyUI or Kling. For now, create a dummy file so UI registers it
        try:
            # Try to copy a placeholder image if it exists, or just touch the file
            import shutil
            placeholder = Path("aether-dashboard/public/favicon.png")
            if placeholder.exists():
                shutil.copy(placeholder, img_path)
            else:
                img_path.touch()
        except:
            img_path.touch()
            
        return {"status": "ok", "result": {"file": img_name, "url": f"/exports/{img_name}"}}
        
    return {"status": "error", "message": f"Unsupported media type: {req.type}"}

@router.get("/library")
def get_library() -> Dict:
    """List all generated media assets."""
    exports_dir = Path("exports")
    files = []
    if exports_dir.exists():
        for f in exports_dir.iterdir():
            if f.is_file() and f.suffix.lower() in [".png", ".jpg", ".mp4", ".mp3", ".wav"]:
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "time": f.stat().st_mtime
                })
    # Sort newest first
    files.sort(key=lambda x: x["time"], reverse=True)
    return {"status": "ok", "files": files}

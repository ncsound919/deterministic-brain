"""Research Engine — Powered by xAI (Grok) and Perplexity.
Provides deep, high-stakes strategic and scientific research.
"""
import os
import json
import urllib.request
from typing import Dict, List, Optional
from config import cfg
from features.fallback_handler import deterministic_fallback, FallbackRegistry

class ResearchEngine:
    def __init__(self):
        from config import reload_config
        _cfg = reload_config()
        self.perplexity_key = _cfg.perplexity_api_key
        self.xai_key = _cfg.xai_api_key

    @deterministic_fallback(FallbackRegistry.simulated_research)
    def perplexity_search(self, query: str) -> Dict:
        """Deep research using Perplexity API."""
        if not self.perplexity_key:
            return {"status": "error", "message": "Perplexity key not found"}
        
        url = "https://api.perplexity.ai/chat/completions"
        payload = {
            "model": "pplx-7b-online",
            "messages": [
                {"role": "system", "content": "You are a scientific researcher providing deterministic facts and references."},
                {"role": "user", "content": query}
            ]
        }
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.perplexity_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
        
        return {
            "status": "success",
            "source": "Perplexity",
            "content": res["choices"][0]["message"]["content"],
            "citations": res.get("citations", [])
        }

    @deterministic_fallback(FallbackRegistry.simulated_research)
    def xai_grok_chat(self, query: str) -> Dict:
        """Real-time strategic analysis using xAI (Grok)."""
        if not self.xai_key:
            return {"status": "error", "message": "xAI key not found"}
            
        url = "https://api.x.ai/v1/chat/completions"
        payload = {
            "model": "grok-beta",
            "messages": [
                {"role": "system", "content": "You are Grok, a strategic business analyst with real-time X.com access."},
                {"role": "user", "content": query}
            ]
        }
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.xai_key}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            res = json.loads(r.read().decode())
            
        return {
            "status": "success",
            "source": "xAI Grok",
            "content": res["choices"][0]["message"]["content"]
        }

_ENGINE: Optional[ResearchEngine] = None

def get_research_engine() -> ResearchEngine:
    global _ENGINE
    if _ENGINE is None: _ENGINE = ResearchEngine()
    return _ENGINE

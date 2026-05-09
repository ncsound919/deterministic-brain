"""Research & Image Clients — Perplexity Pro (browser) + Gemini (API).

Perplexity Pro: Uses browser automation to log in, submit queries, and
extract AI-generated answers with citations. Cookies persisted in
.browser_sessions/perplexity_cookies.json.

Gemini: Uses Google AI Studio free API key for text generation,
research summarization, and image generation (Imagen).
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

from tools.vault_aware_api import get_key


# ═══════════════════════════════════════════════════════════════════════
# Gemini API Client
# ═══════════════════════════════════════════════════════════════════════

class GeminiClient:
    """Google Gemini API — research, summarization, image generation.

    Free tier: 1,500 req/day via Google AI Studio.
    Get key: https://aistudio.google.com/apikey

    Models: gemini-2.0-flash (fast), gemini-2.5-pro (research),
            gemini-2.0-flash-exp (image generation)
    """

    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="gemini", vault_key="api_key",
            env_var="GEMINI_API_KEY", explicit=api_key,
        )

    def _generate(self, model: str, prompt: str,
                  system_instruction: str = "",
                  temperature: float = 0.7,
                  max_tokens: int = 2048) -> Dict:
        if not self.key:
            return {"ok": False, "error": "No Gemini API key. Get one at https://aistudio.google.com/apikey"}

        contents = [{"parts": [{"text": prompt}]}]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        try:
            url = f"{self.BASE}/models/{model}:generateContent"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.key,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
                text = ""
                for candidate in result.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text += part.get("text", "")
                return {
                    "ok": True,
                    "model": model,
                    "text": text,
                    "usage": result.get("usageMetadata", {}),
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def research(self, query: str, depth: str = "pro") -> Dict:
        """Deep research query using gemini-2.5-pro or gemini-2.0-flash."""
        model = "gemini-2.5-pro" if depth == "pro" else "gemini-2.0-flash"
        system = (
            "You are a research assistant. Provide a thorough, well-structured "
            "answer with key facts, analysis, and citations where possible. "
            "Use headings, bullet points, and clear sections."
        )
        return self._generate(model, query, system_instruction=system, max_tokens=4096)

    def summarize(self, text: str, max_words: int = 150) -> Dict:
        """Summarize text concisely."""
        prompt = f"Summarize this in {max_words} words or less:\n\n{text[:10000]}"
        return self._generate(
            "gemini-2.0-flash", prompt,
            system_instruction="You are a summarizer. Be concise and accurate.",
            temperature=0.3,
        )

    def analyze(self, topic: str, context: str = "") -> Dict:
        """Strategic analysis of a topic with optional context."""
        prompt = f"Analyze: {topic}"
        if context:
            prompt += f"\n\nContext: {context}"
        return self._generate(
            "gemini-2.5-pro", prompt,
            system_instruction=(
                "You are a strategic analyst. Provide SWOT-like analysis, "
                "key trends, opportunities, and risks. Be data-driven."
            ),
            max_tokens=4096,
        )

    def brainstorm(self, goal: str, constraints: str = "") -> Dict:
        """Generate creative ideas for a goal."""
        prompt = f"Brainstorm ideas for: {goal}"
        if constraints:
            prompt += f"\nConstraints: {constraints}"
        return self._generate(
            "gemini-2.0-flash", prompt,
            system_instruction=(
                "You are a creative ideation engine. Generate 10+ unique, "
                "actionable ideas. Be specific and practical."
            ),
            temperature=0.9,
            max_tokens=2048,
        )

    def generate_image_prompt(self, description: str) -> Dict:
        """Generate an optimized image generation prompt from a description."""
        prompt = (
            f"Convert this into a detailed, professional image generation prompt "
            f"suitable for DALL-E, Midjourney, or Imagen. Include style, lighting, "
            f"composition, colors, and mood:\n\n{description}"
        )
        return self._generate("gemini-2.0-flash", prompt, max_tokens=512)

    def quick_answer(self, question: str) -> Dict:
        """Fast factual answer."""
        return self._generate(
            "gemini-2.0-flash", question,
            temperature=0.1, max_tokens=1024,
        )


# ═══════════════════════════════════════════════════════════════════════
# Perplexity Pro Browser Client
# ═══════════════════════════════════════════════════════════════════════

class PerplexityClient:
    """Perplexity Pro via browser automation.

    Uses the LiveBrowser (Playwright) to log into perplexity.ai,
    submit research queries, and extract AI answers with citations.

    Requires:
      - Playwright installed (pip install playwright && playwright install chromium)
      - Perplexity Pro login credentials in vault:
        vault.set('perplexity', 'email', '...')
        vault.set('perplexity', 'password', '...')
    """

    LOGIN_URL = "https://www.perplexity.ai/login"
    HOME_URL = "https://www.perplexity.ai"

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._browser: Any = None

    def _ensure_browser(self):
        if self._browser is None:
            from tools.browser.live_controller import LiveBrowser
            self._browser = LiveBrowser(headless=self._headless)
            self._browser.__enter__()
        return self._browser

    def close(self):
        if self._browser:
            self._browser.__exit__(None, None, None)
            self._browser = None

    def _get_credentials(self) -> Dict[str, str]:
        email = get_key(
            vault_category="perplexity", vault_key="email",
        )
        if not email:
            email = get_key(
                vault_category="google", vault_key="email",
            )
        return {
            "email": email,
            "password": get_key(
                vault_category="perplexity", vault_key="password",
            ),
        }

    def login(self) -> Dict:
        """Log into Perplexity via Google OAuth (what Pro users typically use)."""
        creds = self._get_credentials()
        email = creds.get("email")
        password = creds.get("password")

        if not email:
            return {
                "ok": False,
                "error": (
                    "No Perplexity credentials. Store them:\n"
                    "  vault.set('perplexity', 'email', '...')\n"
                    "  vault.set('perplexity', 'password', '...')"
                ),
            }

        browser = self._ensure_browser()

        try:
            browser.navigate("perplexity", self.LOGIN_URL)
            time.sleep(3)

            # Perplexity offers "Continue with Google" as primary login
            # Click the Google sign-in button
            try:
                browser.click(
                    "perplexity",
                    'button:has-text("Google"), div:has-text("Continue with Google")',
                    timeout=5000,
                )
                time.sleep(3)
            except Exception:
                # Fallback: try email/password login
                pass

            # If Google OAuth flow, handle it
            try:
                page = browser._get_page("perplexity")
                if "accounts.google.com" in page.url:
                    # On Google sign-in page
                    browser.fill("perplexity",
                                'input[type="email"]', email, timeout=8000)
                    browser.click("perplexity",
                                 'button:has-text("Next"), #identifierNext', timeout=5000)
                    time.sleep(3)

                    if password:
                        browser.fill("perplexity",
                                    'input[type="password"]', password, timeout=8000)
                        browser.click("perplexity",
                                     'button:has-text("Next"), #passwordNext', timeout=5000)
                        time.sleep(5)
            except Exception as e:
                return {"ok": False, "error": f"Google OAuth failed: {e}"}

            browser.save_cookies("perplexity")
            return {"ok": True, "platform": "perplexity",
                    "current_url": browser._get_page("perplexity").url}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def search(self, query: str, mode: str = "pro") -> Dict:
        """Search Perplexity with Pro mode and extract results.

        Args:
            query: Research question
            mode: 'pro' for deep research, 'auto' for default
        """
        try:
            browser = self._ensure_browser()
            browser.navigate("perplexity", self.HOME_URL)
            time.sleep(3)

            # Find the search input and type the query
            search_selectors = [
                'textarea[placeholder*="Ask"]',
                'textarea[placeholder*="ask"]',
                'input[placeholder*="Ask"]',
                'textarea',
            ]
            for sel in search_selectors:
                try:
                    browser.fill("perplexity", sel, query, timeout=5000)
                    break
                except Exception:
                    continue

            # Submit (Enter key)
            browser.press("perplexity", "Enter")
            time.sleep(8)  # Wait for Pro search to complete

            # Try to select Pro mode if available
            if mode == "pro":
                try:
                    browser.click("perplexity",
                                 'button:has-text("Pro"), div:has-text("Pro Search")',
                                 timeout=3000)
                    time.sleep(2)
                    browser.press("perplexity", "Enter")
                    time.sleep(8)
                except Exception:
                    pass

            # Extract the answer text
            answer = ""
            try:
                answer = browser.get_text(
                    "perplexity",
                    'div[class*="prose"], div[class*="answer"], '
                    'div[class*="response"], main',
                )
            except Exception:
                pass

            # Extract citations
            citations = []
            try:
                text = browser.get_text("perplexity", "body")
                if text.get("ok") and text.get("text"):
                    import re
                    urls = re.findall(r'https?://[^\s<>"]+', text["text"])
                    citations = list(set(urls))[:10]
            except Exception:
                pass

            answer_text = answer.get("text", "") if isinstance(answer, dict) else str(answer)

            return {
                "ok": True,
                "query": query,
                "mode": mode,
                "answer": answer_text[:5000],
                "citations": citations,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "query": query}

    def status(self) -> Dict:
        try:
            browser = self._ensure_browser()
            logged_in = browser.is_logged_in("perplexity", 'textarea[placeholder*="Ask"]')
            return {"configured": True, "logged_in": logged_in}
        except Exception:
            return {"configured": False, "logged_in": False}


# ── Convenience ─────────────────────────────────────────────────────────

def deep_research(query: str, providers: List[str] = None) -> Dict:
    """Research a topic using all available providers.

    Tries: Gemini API → Perplexity browser → plain web fetch.
    Returns structured answer from the first successful provider.
    """
    providers = providers or ["gemini", "perplexity", "web"]
    result = {
        "query": query,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": {},
        "best_answer": "",
        "provider_used": "",
    }

    for provider in providers:
        try:
            if provider == "gemini":
                gc = GeminiClient()
                if gc.key:
                    r = gc.research(query)
                    if r.get("ok"):
                        result["results"]["gemini"] = r["text"][:3000]
                        result["best_answer"] = r["text"]
                        result["provider_used"] = "gemini"
                        break

            elif provider == "perplexity":
                pc = PerplexityClient(headless=True)
                try:
                    pc.login()
                    r = pc.search(query, mode="pro")
                    if r.get("ok") and r.get("answer"):
                        result["results"]["perplexity"] = r["answer"][:3000]
                        result["best_answer"] = r["answer"]
                        result["provider_used"] = "perplexity"
                        result["citations"] = r.get("citations", [])
                        break
                finally:
                    pc.close()

            elif provider == "web":
                from tools.web_fetcher import web_fetch
                r = web_fetch(f"https://www.google.com/search?q={urllib.request.quote(query)}")
                if r.get("text"):
                    result["results"]["web"] = r["text"][:2000]
                    if not result["best_answer"]:
                        result["best_answer"] = r["text"][:2000]
                        result["provider_used"] = "web"

        except Exception as e:
            result["results"][provider] = {"error": str(e)}

    return result

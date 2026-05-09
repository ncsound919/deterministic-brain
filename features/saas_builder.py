"""SaaS Builder — end-to-end research → build → deploy → monetize pipeline.

Stages:
1. RESEARCH — find market opportunities via web/KB
2. BUILD — generate full project from template + research
3. DEPLOY — push to GitHub, deploy to Cloudflare/Vercel
4. MONETIZE — integrate Stripe payments, set pricing
"""
from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


STAGES = ["research", "build", "deploy", "monetize"]


@dataclass
class SaaSProject:
    id: str
    name: str
    idea: str
    stage: str = "research"
    repo_url: str = ""
    deployed_url: str = ""
    stripe_product_id: str = ""
    price_usd: int = 0
    created_at: float = field(default_factory=time.time)
    research_notes: str = ""
    tech_stack: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "idea": self.idea,
            "stage": self.stage, "repo_url": self.repo_url,
            "deployed_url": self.deployed_url, "price_usd": self.price_usd,
            "created_at": self.created_at, "research_notes": self.research_notes,
            "tech_stack": self.tech_stack,
        }


class SaaSBuilder:
    def __init__(self, db_path: str = "saas_projects.json"):
        self.db_path = db_path
        self.projects: Dict[str, SaaSProject] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                for item in data:
                    p = SaaSProject(**item)
                    self.projects[p.id] = p
            except Exception:
                pass

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump([p.to_dict() for p in self.projects.values()], f, indent=2)

    def research(self, topic: str) -> Dict:
        """Research market opportunity using web + KB."""
        findings = []
        try:
            from tools.web_fetcher import WebFetcher
            fetcher = WebFetcher()
            sources = [
                f"https://news.ycombinator.com/item?id=startup",
                f"https://www.indiehackers.com/products?keyword={topic.replace(' ', '+')}",
            ]
            for url in sources[:1]:
                try:
                    text = fetcher.text(url)
                    findings.append(f"Source {url}: {text[:500]}")
                except Exception:
                    findings.append(f"Could not reach {url}")
        except Exception as e:
            findings.append(f"Research error: {e}")

        return {"topic": topic, "findings": findings, "suggested_idea": f"Build a {topic} SaaS"}

    def create_project(self, name: str, idea: str, tech_stack: List[str] = None) -> SaaSProject:
        import hashlib
        pid = hashlib.sha256((name + idea + str(time.time())).encode()).hexdigest()[:12]
        research = self.research(name)
        p = SaaSProject(
            id=pid, name=name, idea=idea,
            stage="research", tech_stack=tech_stack or ["python", "react", "fastapi"],
            research_notes=json.dumps(research.get("findings", [])),
        )
        self.projects[pid] = p
        self._save()
        return p

    def advance_stage(self, project_id: str) -> Optional[SaaSProject]:
        p = self.projects.get(project_id)
        if not p:
            return None
        idx = STAGES.index(p.stage)
        if idx + 1 < len(STAGES):
            p.stage = STAGES[idx + 1]
            self._save()
        return p

    def generate_build_task(self, project_id: str) -> Dict:
        """Generate a build task that uses knowledge bank + templates."""
        p = self.projects.get(project_id)
        if not p:
            return {"error": "project not found"}
        return {
            "query": f"build a {p.idea} SaaS with {', '.join(p.tech_stack)}",
            "project_id": p.id,
            "project_name": p.name,
            "research": p.research_notes,
        }

    def setup_stripe(self, project_id: str, price_usd: int = 9) -> Dict:
        """Generate Stripe integration code."""
        p = self.projects.get(project_id)
        if not p:
            return {"error": "project not found"}
        p.price_usd = price_usd
        p.stage = "monetize"
        self._save()

        return {
            "stripe_setup": {
                "price_usd": price_usd,
                "checkout_code": f"""
import stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@app.post("/create-checkout-session")
async def create_checkout():
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{{
            "price_data": {{
                "currency": "usd",
                "product_data": {{"name": "{p.name}"}},
                "unit_amount": {price_usd * 100},
            }},
            "quantity": 1,
        }}],
        mode="payment",
        success_url="https://{p.deployed_url or 'yourapp.com'}/success",
        cancel_url="https://{p.deployed_url or 'yourapp.com'}/cancel",
    )
    return {{"url": session.url}}
""".strip(),
            }
        }

    def deploy_to_cloudflare(self, project_id: str, pages_project: str = "") -> Dict:
        """Trigger Cloudflare Pages deploy."""
        p = self.projects.get(project_id)
        if not p:
            return {"error": "project not found"}
        try:
            from tools.cloudflare_client import cloudflare_deploy
            result = cloudflare_deploy(p.name, p.repo_url or f"https://github.com/user/{p.name}")
            p.deployed_url = result.get("url", "")
            p.stage = "deploy"
            self._save()
            return result
        except ImportError:
            return {"status": "stub", "message": "Cloudflare client not configured"}
        except Exception as e:
            return {"error": str(e)}

    def list_all(self) -> List[SaaSProject]:
        return list(self.projects.values())


_BUILDER: Optional[SaaSBuilder] = None


def get_saas_builder() -> SaaSBuilder:
    global _BUILDER
    if _BUILDER is None:
        _BUILDER = SaaSBuilder()
    return _BUILDER

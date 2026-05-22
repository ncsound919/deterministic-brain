"""Skill Expander — background Claude/OpenAI skill pack downloading.

Auto-discovers new skill packs from GitHub, downloads them,
registers them with the skill registry, and reports stats.
"""
from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SkillExpander:
    def __init__(self, skill_dir: str = "skill_packs"):
        self.skill_dir = skill_dir
        self.expansion_log: List[Dict] = []
        self._load_log()

    def _load_log(self):
        path = ".skill_expansion.json"
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.expansion_log = json.load(f)
            except Exception:
                pass

    def _save_log(self):
        with open(".skill_expansion.json", "w") as f:
            json.dump(self.expansion_log[-100:], f, indent=2)

    def discover_claude_skills(self) -> List[Dict]:
        """Discover Claude Code skill packs from GitHub topics."""
        results = []
        queries = [
            "language:markdown skill.md Claude Code",
            "topic:skill-pack Claude",
            "anthropic skills SKILL.md",
        ]
        for query in queries[:1]:  # limit to avoid rate limits
            try:
                url = f"https://api.github.com/search/repositories?q={urllib.request.quote(query)}&per_page=10&sort=stars"
                req = urllib.request.Request(url, headers={
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "DeterministicBrain/1.0",
                })
                token = os.getenv("GITHUB_TOKEN", "")
                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read().decode())
                for item in data.get("items", []):
                    results.append({
                        "name": item["name"],
                        "owner": item["owner"]["login"],
                        "url": item["html_url"],
                        "description": item.get("description", ""),
                        "stars": item.get("stargazers_count", 0),
                    })
            except Exception:
                continue
        return results

    def download_skill(self, owner: str, repo: str) -> Optional[str]:
        """Download a skill pack from GitHub as a zip and extract."""
        import shutil

        dest = os.path.join(self.skill_dir, f"imported_{repo}")
        if os.path.exists(dest):
            return dest

        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/zipball/main"
            req = urllib.request.Request(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "DeterministicBrain/1.0",
            })
            token = os.getenv("GITHUB_TOKEN", "")
            if token:
                req.add_header("Authorization", f"Bearer {token}")

            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()

            import zipfile
            import io
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                os.makedirs(dest, exist_ok=True)
                for member in zf.namelist():
                    parts = member.split("/", 1)
                    if len(parts) > 1:
                        target = os.path.join(dest, parts[1])
                        if member.endswith("/"):
                            os.makedirs(target, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target), exist_ok=True)
                            with zf.open(member) as src, open(target, "wb") as dst:
                                shutil.copyfileobj(src, dst)

            self.expansion_log.append({
                "action": "downloaded", "owner": owner, "repo": repo,
                "target": dest, "ts": time.time(),
            })
            self._save_log()
            return dest
        except Exception as e:
            logger.warning(f"Skill download failed {owner}/{repo}: {e}")
            self.expansion_log.append({
                "action": "failed", "owner": owner, "repo": repo,
                "error": str(e), "ts": time.time(),
            })
            self._save_log()
            return None

    def expand(self, max_downloads: int = 3) -> Dict:
        """Discover and download new skill packs."""
        discovered = self.discover_claude_skills()
        downloaded = 0
        downloads = []

        for skill in discovered:
            if downloaded >= max_downloads:
                break
            dest = os.path.join(self.skill_dir, f"imported_{skill['name']}")
            if os.path.exists(dest):
                continue
            result = self.download_skill(skill["owner"], skill["name"])
            if result:
                downloaded += 1
                downloads.append(skill["name"])

        return {
            "discovered": len(discovered),
            "downloaded": downloaded,
            "repos": downloads,
        }

    def refresh_registry(self) -> Dict:
        """Re-discover skills from the skill directory after expansion."""
        try:
            from orchestration.skill_registry import get_skill_registry, reset_skill_registry
            reset_skill_registry()
            sr = get_skill_registry()
            sr.discover()
            return {"skills_total": len(sr.list_all())}
        except Exception as e:
            return {"error": str(e)}

    def get_stats(self) -> Dict:
        return {
            "total_expansions": len(self.expansion_log),
            "last_expansion": self.expansion_log[-1] if self.expansion_log else None,
        }


_EXPANDER: Optional[SkillExpander] = None


def get_expander() -> SkillExpander:
    global _EXPANDER
    if _EXPANDER is None:
        _EXPANDER = SkillExpander()
    return _EXPANDER

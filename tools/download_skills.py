"""Download and import skills from external registries.

Downloads skills from:
- Anthropic Claude Skills: github.com/anthropics/skills
- Hermes Agent Skills: github.com/NousResearch/hermes-agent/tree/main/skills
- OpenClaw Skills: github.com/openclaw/skills
- GitHub Skills: github.com/digitalocean-labs/do-app-platform-skills

Usage:
    python tools/download_skills.py [--source hermes|openclaw|anthropic|github|all]
    python tools/download_skills.py --import-only
"""
from __future__ import annotations
import os
import shutil
import subprocess
import sys
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

REPO_CONFIG = {
    "anthropic": {
        "url": "https://github.com/anthropics/skills",
        "branch": "main",
        "skills_path": "skills",
        "dest": "skill_packs/anthropic_imported",
        "file_pattern": "SKILL.md",
    },
    "hermes": {
        "url": "https://github.com/NousResearch/hermes-agent",
        "branch": "main",
        "skills_path": "skills",
        "dest": "skill_packs/hermes_imported",
        "file_pattern": "SKILL.md",
    },
    "openclaw": {
        "url": "https://github.com/openclaw/skills",
        "branch": "main",
        "skills_path": "skills",
        "dest": "skill_packs/openclaw_imported",
        "file_pattern": "SKILL.md",
    },
    "github": {
        "url": "https://github.com/digitalocean-labs/do-app-platform-skills",
        "branch": "main",
        "skills_path": "skills",
        "dest": "skill_packs/github_imported",
        "file_pattern": "skill.md",
    },
}

CACHE_DIR = ".skill_cache"


def run_cmd(cmd: list[str], cwd: str = None) -> tuple[int, str, str]:
    """Run command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def ensure_cache_dir() -> str:
    """Ensure cache directory exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    return CACHE_DIR


def clone_or_pull(repo_url: str, branch: str, dest: str) -> bool:
    """Clone or update a repository."""
    if os.path.exists(dest):
        log.info(f"  Already exists: {dest}")
        return True
    
    log.info(f"  Cloning {repo_url}...")
    
    code, stdout, stderr = run_cmd(["git", "clone", "--depth", "1", "--branch", branch, repo_url, dest])
    if code == 0:
        log.info(f"  Clone successful")
        return True
    else:
        log.warning(f"  Clone failed: {stderr[:200] if stderr else 'unknown error'}")
        return False


def import_skills(source: str, config: dict) -> int:
    """Import skills from a source."""
    log.info(f"\n=== Importing {source.upper()} ===")
    
    temp_dir = f".temp_{source}"
    os.makedirs(temp_dir, exist_ok=True)
    
    if not clone_or_pull(config["url"], config["branch"], temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
        return 0
    
    skills_path = os.path.join(temp_dir, config["skills_path"])
    if not os.path.exists(skills_path):
        log.warning(f"  Skills path not found: {skills_path}")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return 0
    
    dest_root = config["dest"]
    os.makedirs(dest_root, exist_ok=True)
    
    imported = 0
    for category in os.listdir(skills_path):
        category_path = os.path.join(skills_path, category)
        if not os.path.isdir(category_path):
            continue
        
        for skill in os.listdir(category_path):
            skill_src = os.path.join(category_path, skill)
            if not os.path.isdir(skill_src):
                continue
            
            skill_file = os.path.join(skill_src, config["file_pattern"])
            if not os.path.exists(skill_file):
                continue
            
            skill_id = f"{source}_{category}_{skill}".replace("/", "_")[:50]
            skill_dest = os.path.join(dest_root, skill_id)
            os.makedirs(skill_dest, exist_ok=True)
            
            dest_file = os.path.join(skill_dest, "SKILL.md")
            shutil.copy2(skill_file, dest_file)
            imported += 1
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    log.info(f"  Imported {imported} skills to {dest_root}")
    return imported


def main():
    parser = argparse.ArgumentParser(description="Download and import external skills")
    parser.add_argument(
        "--source",
        choices=["anthropic", "hermes", "openclaw", "github", "all"],
        default="all",
        help="Source to download from",
    )
    parser.add_argument(
        "--import-only",
        action="store_true",
        help="Only import from cache, don't download",
    )
    args = parser.parse_args()
    
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base)
    
    sources = [args.source] if args.source != "all" else list(REPO_CONFIG.keys())
    
    total = 0
    for source in sources:
        if source in REPO_CONFIG:
            count = import_skills(source, REPO_CONFIG[source])
            total += count
    
    log.info(f"\n=== Summary ===")
    log.info(f"Total skills imported: {total}")
    log.info(f"Run: python -c \"from orchestration import get_skill_registry; r = get_skill_registry(); r.discover(); print(r.list_by_backend())\"")


if __name__ == "__main__":
    main()
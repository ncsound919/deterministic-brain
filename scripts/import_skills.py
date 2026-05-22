"""Skill Importer — downloads open source skills and converts to brain format.

Sources:
  anthropics/skills        — 17 design/coding skills (SKILL.md)
  openai/skills            — 30+ agent skills (SKILL.md)
  obra/superpowers         — 15 testing/debugging/collab skills (SKILL.md)
  CoworkedShawn/openclaw-skills — 7 agent skills (SKILL.md)
  NousResearch/Hermes-Function-Calling — 5-6 function-calling tools (@tool)

Converts all to the brain's YAML frontmatter + Markdown format under skill_packs/.
"""

from __future__ import annotations
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List


SKILL_PACKS_DIR = Path("skill_packs")
SKILL_PACKS_DIR.mkdir(exist_ok=True)

REPOS = [
    {
        "name": "anthropic",
        "url": "https://github.com/anthropics/skills.git",
        "branch": "main",
        "skills_glob": "skills/*/SKILL.md",
        "backend": "claude",
    },
    {
        "name": "openai",
        "url": "https://github.com/openai/skills.git",
        "branch": "main",
        "skills_glob": ".system/*/SKILL.md .curated/*/SKILL.md .experimental/*/SKILL.md",
        "backend": "openclaw",
    },
    {
        "name": "superpowers",
        "url": "https://github.com/obra/superpowers.git",
        "branch": "main",
        "skills_glob": "skills/*/SKILL.md",
        "backend": "local",
    },
    {
        "name": "openclaw",
        "url": "https://github.com/CoworkedShawn/openclaw-skills.git",
        "branch": "main",
        "skills_glob": "**/SKILL.md",
        "backend": "openclaw",
    },
]

YAML_REGEX = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def normalize_frontmatter(yaml_text: str, backend: str) -> str:
    """Convert any SKILL.md YAML frontmatter to the brain's format."""
    # Parse YAML (simple key-value extraction, no heavy dependency)
    fields = {}
    for line in yaml_text.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            fields[key] = value

    # Build brain-formatted frontmatter
    skill_name = (
        fields.get("skill")
        or fields.get("name")
        or "unknown"
    )
    # Clean skill name: lowercase, replace spaces with hyphens
    skill_id = re.sub(r"[^a-z0-9-]", "", skill_name.lower().replace(" ", "-"))[:40]

    description = fields.get("description", "")
    metadata = fields.get("metadata", "")
    version = fields.get("version", "1.0")

    lines = ["---"]
    lines.append(f"skill: {skill_id}")
    lines.append(f"version: {version}")
    lines.append(f"backend: {backend}")
    lines.append(f"backend_skill_id: \"{skill_name}\"")
    lines.append(f"description: \"{description}\"")
    # Extract inputs from description heuristics
    inputs = _infer_inputs(description)
    if inputs:
        lines.append("inputs:")
        for inp in inputs:
            lines.append(f"  {inp}: string")
    lines.append("tools: []")
    lines.append("audit: []")
    lines.append("monte_carlo: false")
    lines.append("---")
    return "\n".join(lines)


def _infer_inputs(description: str) -> List[str]:
    """Heuristically extract input parameter names from a description."""
    # Look for quoted/backticked params or common patterns
    params = set()
    # Quoted args
    for match in re.finditer(r"`(\w+)`", description):
        params.add(match.group(1))
    # Common coding params
    common = ["name", "code", "file", "path", "url", "input", "output",
              "language", "framework", "type"]
    desc_lower = description.lower()
    for p in common:
        if p in desc_lower.split():
            params.add(p)
    # Filter noise words
    noise = {"a", "an", "the", "is", "and", "or", "of", "to", "in", "for",
             "with", "on", "this", "that", "it", "be", "use", "can", "how"}
    return [p for p in sorted(params) if p not in noise][:5]


def git_clone(url: str, branch: str, target: Path) -> bool:
    """Clone a git repo shallowly."""
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, url, str(target)],
            capture_output=True, check=True, timeout=60,
        )
        return True
    except Exception as e:
        print(f"  ERR Clone failed for {url.split('/')[-1].replace('.git','')}: {e}")
        return False


def extract_frontmatter_and_body(content: str) -> tuple[str, str]:
    """Split SKILL.md into YAML frontmatter and Markdown body."""
    match = YAML_REGEX.match(content)
    if match:
        return match.group(1), content[match.end():].strip()
    return "", content


def import_repo(repo: dict, tmp_dir: Path) -> int:
    """Download and import a single repo's skills. Returns count imported."""
    repo_name = repo["name"]
    print(f"\n[*] Importing {repo_name}...")

    clone_dir = tmp_dir / repo_name
    if not git_clone(repo["url"], repo["branch"], clone_dir):
        return 0

    dest_dir = SKILL_PACKS_DIR / repo_name
    dest_dir.mkdir(exist_ok=True)

    count = 0
    for glob_pattern in repo["skills_glob"].split():
        for skill_path in clone_dir.glob(glob_pattern):
            try:
                content = skill_path.read_text(encoding="utf-8", errors="replace")
                frontmatter, body = extract_frontmatter_and_body(content)
                new_fm = normalize_frontmatter(frontmatter, repo["backend"])

                # Get skill name from path
                skill_name = skill_path.parent.name if skill_path.parent.name != repo_name else skill_path.stem
                skill_name = re.sub(r"[^a-zA-Z0-9_-]", "", skill_name)[:40]

                skill_dir = dest_dir / skill_name
                skill_dir.mkdir(exist_ok=True)

                # Write converted SKILL.md
                skill_file = skill_dir / "SKILL.md"
                full_content = f"{new_fm}\n\n{body}\n"
                skill_file.write_text(full_content, encoding="utf-8")

                # Copy companion files (templates, scripts, etc.)
                for companion in skill_path.parent.glob("*"):
                    if companion.name != "SKILL.md" and companion.is_file():
                        shutil.copy2(companion, skill_dir / companion.name)

                count += 1
                print(f"  OK  {skill_name}")
            except Exception as e:
                print(f"  ERR {skill_path.relative_to(clone_dir)}: {e}")

    print(f"  Imported {count} skills to {dest_dir}")
    return count


def import_hermes_skills(tmp_dir: Path) -> int:
    """Import Hermes function-calling skills (Python @tool format)."""
    print("\n[*] Importing hermes...")

    clone_dir = tmp_dir / "hermes"
    if not git_clone(
        "https://github.com/NousResearch/Hermes-Function-Calling.git",
        "main", clone_dir,
    ):
        return 0

    dest_dir = SKILL_PACKS_DIR / "hermes"
    dest_dir.mkdir(exist_ok=True)

    # The Hermes repo has functions in a specific module
    func_files = list(clone_dir.glob("**/functions.py")) + list(clone_dir.glob("**/function*.py"))
    if not func_files:
        # Try to find any Python file with @tool decorator
        for f in clone_dir.glob("**/*.py"):
            content = f.read_text(errors="replace")
            if "@tool" in content or "def get_" in content:
                func_files.append(f)

    count = 0
    for func_file in func_files[:20]:  # limit to 20 files
        try:
            content = func_file.read_text(errors="replace")
            # Extract functions with @tool decorator or docstrings
            func_pattern = re.compile(
                r'(?:@tool\([^)]*\)\s*\n)?def (\w+)\(([^)]*)\):\s*\n\s*"""([^"]*)"""',
                re.DOTALL,
            )
            for match in func_pattern.finditer(content):
                func_name = match.group(1)
                params = match.group(2).strip()
                docstring = match.group(3).strip()

                skill_dir = dest_dir / func_name
                skill_dir.mkdir(exist_ok=True)

                # Convert to SKILL.md
                inputs = {}
                for p in params.split(","):
                    p = p.strip()
                    if ":" in p:
                        name, _, typ = p.partition(":")
                        inputs[name.strip()] = typ.strip()
                    elif p and p != "self":
                        inputs[p] = "string"

                fm_lines = ["---"]
                fm_lines.append(f"skill: hermes-{func_name}")
                fm_lines.append("version: 1.0")
                fm_lines.append("backend: hermes")
                fm_lines.append(f"backend_skill_id: \"{func_name}\"")
                fm_lines.append(f"description: \"{docstring.split(chr(10))[0]}\"")
                if inputs:
                    fm_lines.append("inputs:")
                    for k, v in inputs.items():
                        fm_lines.append(f"  {k}: {v}")
                fm_lines.append("tools: [function_call]")
                fm_lines.append("audit: []")
                fm_lines.append("monte_carlo: false")
                fm_lines.append("---")
                fm_lines.append("")
                fm_lines.append(docstring)
                fm_lines.append("")
                fm_lines.append("```python")
                fm_lines.append("# See source at Hermes-Function-Calling repo")
                fm_lines.append(f"# Function: {func_name}({params})")
                fm_lines.append("```")

                (skill_dir / "SKILL.md").write_text("\n".join(fm_lines))
                count += 1
                print(f"  OK  hermes-{func_name}")
        except Exception as e:
            print(f"  ERR {func_file.name}: {e}")

    print(f"  Imported {count} hermes skills to {dest_dir}")
    return count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import open source skills into the brain")
    parser.add_argument("--full", action="store_true",
                        help="Also download the 2,810-skill marketplace (large)")
    parser.add_argument("--source", type=str,
                        help="Only import a specific source (anthropic,openai,superpowers,openclaw,hermes)")
    args = parser.parse_args()

    tmp_dir = Path(tempfile.mkdtemp(prefix="skill_import_"))
    total = 0

    sources = REPOS.copy()
    if args.source:
        sources = [r for r in sources if r["name"] == args.source]
        if not sources:
            print(f"Unknown source: {args.source}. Options: anthropic,openai,superpowers,openclaw,hermes")
            return

    for repo in sources:
        total += import_repo(repo, tmp_dir)

    # Hermes is always included since it's a different format
    if not args.source or args.source == "hermes":
        total += import_hermes_skills(tmp_dir)

    # Full marketplace (large)
    if args.full:
        marketplace = {
            "name": "marketplace",
            "url": "https://github.com/jeremylongshore/claude-code-plugins-plus-skills.git",
            "branch": "main",
            "skills_glob": "*/skills/*/SKILL.md",
            "backend": "claude",
        }
        total += import_repo(marketplace, tmp_dir)

    # Cleanup
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"\nTotal skills imported: {total}")
    print(f"   Location: {SKILL_PACKS_DIR.resolve()}")
    print("   Run `python main.py` to use them")


if __name__ == "__main__":
    main()

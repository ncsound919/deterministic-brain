"""Quick import of OpenAI skills from already-cloned repo."""
import re
import shutil
from pathlib import Path

src = Path.home() / "AppData/Local/Temp/openai_skills_check/skills"
dest = Path("skill_packs/openai")
dest.mkdir(exist_ok=True)

YAML_REGEX = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
count = 0

for tier in [".system", ".curated", ".experimental"]:
    tier_dir = src / tier
    if not tier_dir.exists():
        continue
    for skill_dir in sorted(tier_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            match = YAML_REGEX.match(content)
            fm = match.group(1) if match else ""
            body = content[match.end():].strip() if match else content

            skill_name = re.sub(r"[^a-z0-9-]", "", skill_dir.name.lower())[:40]

            sd = dest / skill_name
            sd.mkdir(exist_ok=True)

            fm_lines = [
                "---",
                f"skill: {skill_name}",
                "version: 1.0",
                "backend: openclaw",
                f'backend_skill_id: "{skill_dir.name}"',
                'description: ""',
                "tools: []",
                "audit: []",
                "monte_carlo: false",
                "---",
            ]
            (sd / "SKILL.md").write_text("\n".join(fm_lines) + "\n\n" + body, encoding="utf-8")

            # Copy companion files
            for companion in skill_dir.iterdir():
                if companion.is_file() and companion.name != "SKILL.md":
                    shutil.copy2(companion, sd / companion.name)

            count += 1
            print(f"  OK  openai/{skill_name}")
        except Exception as e:
            print(f"  ERR {skill_dir.name}: {e}")

print(f"\nImported {count} OpenAI skills to skill_packs/openai")

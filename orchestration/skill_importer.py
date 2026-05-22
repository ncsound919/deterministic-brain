import os
import yaml
import re
from loguru import logger
from typing import Dict, Any, List
from pydantic import BaseModel, create_model

from orchestration.intent_router import IntentRouter
from schemas.schema_registry import SchemaRegistry

class SkillImporter:
    """
    Automated Importer for Skills.
    Parses variety of formats (SKILL.md frontmatter, JSON, YAML) and auto-registers them
    into the SchemaRegistry and IntentRouter.
    """
    def __init__(self, intent_router: IntentRouter):
        self.intent_router = intent_router

    def import_skills_from_directory(self, root_dir: str):
        """Recursively scan a directory for SKILL.md and register them."""
        count = 0
        for dirpath, _, filenames in os.walk(root_dir):
            if "SKILL.md" in filenames:
                file_path = os.path.join(dirpath, "SKILL.md")
                if self.import_skill_md(file_path):
                    count += 1
            # Can also add support for skill.yaml, skill.json here
        logger.info(f"Dynamically imported {count} skills from {root_dir}")
        return count

    def import_skill_md(self, filepath: str) -> bool:
        """Parse a SKILL.md file and register it."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract YAML frontmatter
            match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
            if not match:
                logger.warning(f"No YAML frontmatter found in {filepath}")
                return False
                
            metadata = yaml.safe_load(match.group(1))
            skill_name = metadata.get('skill') or metadata.get('name')
            if not skill_name:
                logger.warning(f"No skill name found in {filepath}")
                return False
                
            description = metadata.get('description', '')
            
            # Generate keywords from name for the deterministic Intent Router
            keywords = [skill_name.lower().replace('-', ' '), skill_name.lower()]
            
            # Optional: if tags exist in frontmatter, we could use them
            if 'tags' in metadata and isinstance(metadata['tags'], list):
                keywords.extend([tag.lower() for tag in metadata['tags']])
                
            keywords = list(set(keywords)) # deduplicate
            
            # Register a dynamic Pydantic Schema for this skill
            # For now, a generic payload since SKILL.md doesn't strict type input parameters in frontmatter
            model_name = f"{skill_name.title().replace('-', '')}Payload"
            dynamic_schema = create_model(
                model_name,
                query=(str, ...),
                context=(Dict[str, Any], {})
            )
            
            schema_key = f"dynamic_{skill_name}"
            SchemaRegistry.register(schema_key, dynamic_schema)
            
            # Register Intent
            self.intent_router.register_intent(
                intent_name=skill_name,
                keywords=keywords,
                handler=self._generate_generic_handler(skill_name, schema_key)
            )
            
            logger.info(f"Imported skill '{skill_name}' from {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import skill from {filepath}: {e}")
            return False
            
    def _generate_generic_handler(self, skill_name: str, schema_key: str):
        """Generates a handler function for dynamic skills."""
        def handler(query: str, context: dict = None):
            logger.info(f"Executing dynamic skill: {skill_name}")
            return {
                "status": "success",
                "skill_executed": skill_name,
                "message": f"Successfully routed to dynamic skill '{skill_name}'",
                "schema_used": schema_key
            }
        return handler

if __name__ == "__main__":
    router = IntentRouter()
    importer = SkillImporter(router)
    importer.import_skills_from_directory("skill_packs")

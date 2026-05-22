from pydantic import BaseModel
from typing import Optional, Dict, Any
from loguru import logger
from schemas.schema_registry import SchemaRegistry
from orchestration.intent_router import IntentRouter
import subprocess

class CLIAnythingRequest(BaseModel):
    """Schema for CLI-Anything requests."""
    target_path: str
    refine_prompt: Optional[str] = None
    action: str = "build" # 'build', 'refine', or 'validate'

# Auto-register schema
SchemaRegistry.register("cli_anything", CLIAnythingRequest)

def handle_cli_anything(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Handler for CLI-Anything intents.
    It expects semantic_layer to have populated context with the parsed schema,
    or we parse it here. For simplicity, we assume context['parsed_data'] has the payload,
    or we do a rudimentary deterministic parse here if not using semantic_layer.
    """
    logger.info("Handling CLI-Anything workflow...")
    
    # In a full flow, semantic_layer parses this.
    # We do a basic deterministic extraction here for the wrapper demonstration.
    import re
    target_path = ""
    action = "build"
    refine_prompt = None
    
    path_match = re.search(r'(?:for|path|repo)\s+([./\w-]+)', query)
    if path_match:
        # If the user literally types 'path ./gimp', we want to capture ./gimp, not 'path'
        # The group(1) captures whatever comes after 'for ', 'path ', or 'repo '
        target = path_match.group(1)
        if target.lower() in ["path", "repo"]:
            # Maybe they said 'for path ./gimp', try another match
            alt_match = re.search(r'(?:for|path|repo)\s+(?:path|repo)?\s*([./\w-]+)', query)
            if alt_match:
                target = alt_match.group(1)
        target_path = target
    
    if "refine" in query.lower():
        action = "refine"
        refine_match = re.search(r'refine.*?with\s+(.*)', query, re.IGNORECASE)
        if refine_match:
            refine_prompt = refine_match.group(1)
            
    if "validate" in query.lower():
        action = "validate"
        
    if not target_path:
        return {"status": "failed", "reason": "No target path provided for CLI-Anything."}
        
    try:
        # Validate through Schema Registry
        payload = {
            "target_path": target_path,
            "action": action,
            "refine_prompt": refine_prompt
        }
        validated_req = SchemaRegistry.validate_and_parse("cli_anything", payload)
        
        logger.info(f"Triggering CLI-Anything action '{validated_req.action}' on path '{validated_req.target_path}'")
        
        # Here we would normally use subprocess to call the actual CLI-Anything python script
        # e.g., subprocess.run(["python", "-m", "cli_anything", validated_req.target_path])
        
        return {
            "status": "success",
            "action_taken": f"cli_anything_{validated_req.action}",
            "target": validated_req.target_path,
            "refinement": validated_req.refine_prompt
        }
        
    except ValueError as e:
        logger.error(f"Schema validation failed: {e}")
        return {"status": "failed", "reason": str(e)}

def register_cli_anything_skill(intent_router: IntentRouter):
    """Register the CLI-Anything skill to the given router."""
    keywords = [
        "cli-anything", "cli anything", "generate cli", 
        "build a cli", "wrap cli", "refine cli"
    ]
    intent_router.register_intent(
        intent_name="cli_anything",
        keywords=keywords,
        handler=handle_cli_anything
    )
    logger.info("CLI-Anything skill wrapped and registered.")

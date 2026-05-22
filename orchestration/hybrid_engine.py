from loguru import logger

# Import the 4 pillars of the Hybrid Deterministic Architecture
from orchestration.confidence_routing import ConfidenceRouter
from orchestration.semantic_layer import SemanticLayer
from orchestration.intent_router import IntentRouter
from schemas.schema_registry import SchemaRegistry
from orchestration.skill_importer import SkillImporter
from skills.cli_anything import register_cli_anything_skill
from skills.content_creation import register_content_creation_skill
from skills.knowledge_synthesis import register_knowledge_synthesis_skill

class HybridDeterministicEngine:
    """
    The main orchestrator implementing a modular, hybrid, and layered approach.
    Retains the speed of deterministic logic while introducing flexibility.
    
    Pillars implemented:
    1. Countering Ambiguity: Confidence Fallbacks & Layered Safeguards (ConfidenceRouter)
    2. Unstructured Data Parsing: Semantic Layer & Micro-LLM Calls (SemanticLayer)
    3. Solving Fragile Maintenance: Central Schema Registry (SchemaRegistry)
    4. Improving User Interaction: Intent Routing & Structured UI Feedback (IntentRouter)
    """
    
    def __init__(self):
        self.confidence_router = ConfidenceRouter(threshold=0.85)
        self.semantic_layer = SemanticLayer()
        self.intent_router = IntentRouter()
        self.skill_importer = SkillImporter(self.intent_router)
        
        # Load dynamic skills
        self.skill_importer.import_skills_from_directory("skill_packs")
        
        # Load explicit core skills
        register_cli_anything_skill(self.intent_router)
        register_content_creation_skill(self.intent_router)
        register_knowledge_synthesis_skill(self.intent_router)
        
        # Setup basic intents
        self._setup_intents()
        # Setup basic deterministic rules with fallbacks
        self._setup_confidence_routes()

    def _setup_intents(self):
        """Setup Intent Routing (Improving User Interaction)"""
        self.intent_router.register_intent(
            "support_ticket", 
            ["ticket", "issue", "help", "broken"],
            self.handle_support_ticket
        )
        self.intent_router.register_intent(
            "process_email",
            ["email", "message", "inbox"],
            self.handle_email
        )
        self.intent_router.register_intent(
            "pr_review",
            ["review", "pull request", "pr", "code"],
            self.handle_pr_review
        )

    def _setup_confidence_routes(self):
        """Setup Confidence Fallbacks (Countering Ambiguity)"""
        # A simple deterministic rule that tries to calculate priority based on length
        def deterministic_priority_check(data: dict):
            issue_text = data.get("issue", "")
            if len(issue_text) < 10:
                return {"priority": 1}, 0.9 # High confidence it's a simple test/short issue
            elif "urgent" in issue_text.lower():
                return {"priority": 5}, 1.0 # High confidence it's urgent
            # Low confidence for anything else
            return {"priority": 3}, 0.4
            
        def fallback_llm_priority_check(data: dict):
            logger.info("Human/LLM fallback invoked to determine priority")
            return {"priority": 4} # Assume LLM reasoned it out

        self.confidence_router.register_route(
            "priority_evaluation",
            deterministic_priority_check,
            fallback_llm_priority_check
        )

    def handle_support_ticket(self, query: str, context: dict):
        logger.info("Handling support ticket workflow...")
        # Step 1: Use Semantic Layer to extract data (Handling Unstructured Data)
        raw_data = self.semantic_layer.process_raw_data(query, "ticket")
        
        # Step 2: Validate against Schema Registry (Solving Fragile Maintenance)
        try:
            structured_ticket = SchemaRegistry.validate_and_parse("ticket", raw_data)
        except ValueError as e:
            # Turn Failures into Guardrails: record this edge case
            logger.error(f"Schema validation failed. Recording edge case. Error: {e}")
            return {"status": "failed", "reason": str(e)}
            
        # Step 3: Use Confidence Routing for business logic (Countering Ambiguity)
        eval_result = self.confidence_router.execute("priority_evaluation", structured_ticket.model_dump())
        
        return {
            "status": "success",
            "ticket_id": structured_ticket.id,
            "priority_assigned": eval_result.data["priority"],
            "fallback_used": eval_result.fallback_triggered
        }

    def handle_email(self, query: str, context: dict):
        logger.info("Handling email workflow...")
        raw_data = self.semantic_layer.process_raw_data(query, "email")
        try:
            email_obj = SchemaRegistry.validate_and_parse("email", raw_data)
            return {"status": "email_processed", "subject": email_obj.subject}
        except ValueError as e:
             return {"status": "failed", "reason": str(e)}

    def handle_pr_review(self, query: str, context: dict):
        logger.info("Handling PR Code Review workflow...")
        # Step 1: Use Semantic Layer
        raw_data = self.semantic_layer.process_raw_data(query, "pr_review")
        
        # Step 2: Validate against Schema Registry
        try:
            pr_obj = SchemaRegistry.validate_and_parse("pr_review", raw_data)
        except ValueError as e:
            logger.error(f"Schema validation failed for PR Review. Error: {e}")
            return {"status": "failed", "reason": str(e)}
            
        # Step 3: Trigger external 'agent-reviews' subprocess / CLI wrap
        # Here we mock the deterministic call out to the agent-reviews skill
        logger.info(f"Delegating to 'agent-reviews' skill for repo: {pr_obj.repo_name}, URL: {pr_obj.pr_url}")
        
        return {
            "status": "success",
            "action_taken": "triggered_agent_reviews_cli",
            "pr_url": pr_obj.pr_url,
            "focus_areas": pr_obj.focus_areas
        }


    def process_user_input(self, user_text: str):
        """
        Main entry point for user interaction.
        """
        logger.info(f"Engine processing input: {user_text}")
        # Intent Routing
        response = self.intent_router.route_query(user_text)
        return response

if __name__ == "__main__":
    engine = HybridDeterministicEngine()
    
    print("\n--- Test 1: Intent Routing & Deterministic Success ---")
    res1 = engine.process_user_input("I have an urgent issue with my account")
    print(res1)
    
    print("\n--- Test 2: Structured UI Feedback Fallback ---")
    res2 = engine.process_user_input("What is the meaning of life?")
    print(res2)
    
    print("\n--- Test 3: PR Review Skill Integration ---")
    res3 = engine.process_user_input("Can you review the PR for repo deterministic-brain url is https://github.com/abc/abc/pull/1")
    print(res3)
    
    print("\n--- Test 4: Dynamic SKILL.md Import (awesome-openclaw-skills) ---")
    res4 = engine.process_user_input("I am executing systematic debugging")
    print(res4)
    
    print("\n--- Test 5: CLI-Anything Wrapper Integration ---")
    res5 = engine.process_user_input("Please build a cli for path ./gimp using cli-anything")
    print(res5)

    print("\n--- Test 6: Content Creation Engine & Crons ---")
    res6 = engine.process_user_input("Create a hood alchemy podcast about AI Disruption and schedule it every week")
    print(res6)

    print("\n--- Test 7: Knowledge Synthesis Engine ---")
    res7 = engine.process_user_input("Synthesize books about Sovereign Agents from drive and generate a plan")
    print(res7)

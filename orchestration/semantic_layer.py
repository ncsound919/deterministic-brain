import re
import json
from typing import Dict, Any, Optional
from loguru import logger


class MicroLLMParse:
    """Schema-driven text -> structured object parsing via local Gemma."""

    SCHEMAS = {
        "ticket": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Ticket ID (e.g. TKT-123)"},
                "issue": {"type": "string", "description": "One-sentence issue description"},
                "priority": {"type": "integer", "description": "1=critical, 2=high, 3=medium, 4=low"},
                "customer_id": {"type": "string", "description": "Customer identifier"},
            },
            "required": ["issue"],
        },
        "pr_review": {
            "type": "object",
            "properties": {
                "pr_url": {"type": "string", "description": "URL of the pull request"},
                "repo_name": {"type": "string", "description": "Repository name"},
                "focus_areas": {"type": "array", "items": {"type": "string"}, "description": "Areas to focus on during review"},
                "strict_mode": {"type": "boolean", "description": "Whether to apply strict review standards"},
            },
            "required": ["pr_url"],
        },
        "email": {
            "type": "object",
            "properties": {
                "sender": {"type": "string", "description": "Email sender address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body text"},
                "is_urgent": {"type": "boolean", "description": "Whether the email is marked urgent"},
            },
            "required": ["sender"],
        },
        "support_ticket": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Support ticket identifier"},
                "category": {"type": "string", "description": "Issue category (bug, feature, billing, etc.)"},
                "summary": {"type": "string", "description": "Brief description of the issue"},
                "urgency": {"type": "string", "description": "Urgency level (critical, high, medium, low)"},
            },
            "required": ["summary"],
        },
    }

    def __init__(self):
        self._gemma = None

    def _get_gemma(self):
        if self._gemma is None:
            from tools.local_gemma import get_gemma
            self._gemma = get_gemma()
        return self._gemma

    def parse(self, text: str, target_schema_name: str) -> Dict[str, Any]:
        schema = self.SCHEMAS.get(target_schema_name.lower(), {})
        schema_str = json.dumps(schema, indent=2)

        prompt = (
            f"Parse the following text into a JSON object matching this schema.\n"
            f"Return ONLY valid JSON, no explanations.\n\n"
            f"Schema:\n{schema_str}\n\n"
            f"Text:\n{text}\n\n"
            f"JSON output:"
        )

        gemma = self._get_gemma()
        if gemma.is_available():
            try:
                result = gemma.complete(prompt, n_predict=192, temperature=0.05)
                if result:
                    parsed = json.loads(result.strip())
                    logger.info(f"Micro-LLM parsed {target_schema_name}: {list(parsed.keys())}")
                    return parsed
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Gemma parse failed for {target_schema_name}: {e}")

        return self._fallback(target_schema_name, text)

    def _fallback(self, schema_name: str, text: str) -> Dict[str, Any]:
        if "ticket" in schema_name.lower():
            return {"id": "TKT-UNKNOWN", "issue": text[:200], "priority": 3, "customer_id": "UNKNOWN"}
        elif "pr_review" in schema_name.lower():
            urls = re.findall(r"https?://[^\s]+", text)
            return {"pr_url": urls[0] if urls else "", "repo_name": "unknown", "focus_areas": ["general"], "strict_mode": False}
        elif "email" in schema_name.lower():
            return {"sender": "unknown", "subject": "", "body": text, "is_urgent": "urgent" in text.lower()}
        return {}


_micro_llm: Optional[MicroLLMParse] = None


def micro_llm_parse(text: str, target_schema_name: str) -> Dict[str, Any]:
    global _micro_llm
    if _micro_llm is None:
        _micro_llm = MicroLLMParse()
    return _micro_llm.parse(text, target_schema_name)


class SemanticLayer:
    """
    Handling Unstructured Data Parsing:
    Translates raw data into standardized objects for the agent to reliably interpret.
    Uses Deterministic Extractors first, and Hybrid "Micro-LLM" calls as a fallback.
    """

    @staticmethod
    def extract_deterministic(text: str, pattern: str) -> Optional[str]:
        """Deterministic Extractor using Regex."""
        match = re.search(pattern, text)
        if match:
            return match.group(1) if len(match.groups()) > 0 else match.group(0)
        return None

    def process_raw_data(self, raw_text: str, schema_name: str) -> Dict[str, Any]:
        """
        Semantic Layering: Attempt deterministic extraction, fallback to Micro-LLM.
        """
        logger.debug(f"Processing raw data for semantic layer: {schema_name}")

        structured_data = {}
        if schema_name == "email":
            sender = self.extract_deterministic(raw_text, r"From:\s*([^\n]+)")
            subject = self.extract_deterministic(raw_text, r"Subject:\s*([^\n]+)")
            if sender and subject:
                structured_data = {
                    "sender": sender.strip(),
                    "subject": subject.strip(),
                    "body": raw_text,
                    "is_urgent": "urgent" in raw_text.lower()
                }
                logger.info("Successfully parsed deterministically.")
                return structured_data

        if schema_name == "pr_review":
            url = self.extract_deterministic(raw_text, r"https?://[^\s]+")
            repo = self.extract_deterministic(raw_text, r"repo\s+([a-zA-Z0-9_-]+)")
            if url and repo:
                structured_data = {
                    "pr_url": url,
                    "repo_name": repo,
                    "focus_areas": ["security", "performance"],
                    "strict_mode": False
                }
                logger.info("Successfully parsed PR review request deterministically.")
                return structured_data

        logger.info("Deterministic extraction incomplete. Falling back to Micro-LLM.")
        structured_data = micro_llm_parse(raw_text, schema_name)
        return structured_data

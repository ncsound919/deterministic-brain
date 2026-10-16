"""CRM skills — deterministic handlers for the CRM tool packs.

``skill_packs/business/crm-contact`` and ``skill_packs/business/crm-pipeline``
are prose skill.md files. ``LocalSkillBackend`` can only render Jinja
templates, so both fell through to the LLM fallback and failed with
``"No LLM API key configured"`` — the stores (``crm/contacts.json``,
``crm/pipeline.json``) were never touched by anything.

This module is the deterministic implementation, registered on the brain's
IntentRouter the same way :mod:`skills.content_creation` is. It implements the
grammar below and refuses anything it cannot parse rather than guessing:

    create contact Dana Reed email dana@acme.test at Acme tag smb, outbound
    update contact dana@acme.test status customer
    search contacts tag smb
    list contacts
    create deal Acme pilot for dana@acme.test stage proposal value 12000
    move deal <deal_id> to closed
    forecast pipeline

Unknown keys and unrecognised actions return ``{"status": "failed", ...}`` —
a malformed CRM request must never look like a completed one.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from loguru import logger
from schemas.schema_registry import SchemaRegistry
from orchestration.intent_router import IntentRouter
from pydantic import BaseModel

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

#: Every token that introduces a key/value pair in either grammar, plus the
#: connectors that terminate a value ("email" before an address, "for" before
#: a contact, "to" before a stage). A value runs until the next one of these.
_TERMINATORS = {
    "at", "company", "tag", "tags", "tagged", "status", "state",
    "stage", "value", "worth", "deal", "deals", "for", "to", "email",
}

#: Leading filler removed before the payload is parsed.
_STRIP_LEAD = re.compile(
    r"^\s*(?:please\s+)?(?:can\s+you\s+)?(?:add|create|new|make|log|register|record)\s+"
    r"(?:a\s+|an\s+|the\s+)?(?:new\s+)?",
    re.IGNORECASE,
)
_STRIP_QUERY_LEAD = re.compile(
    r"^\s*(?:show|list|find|search|get|give\s+me)\s+(?:me\s+)?(?:all\s+|the\s+)?", re.IGNORECASE
)
#: Leftover connectors ("create deal **for** ...") that are not payload.
_STRIP_CONNECTORS = re.compile(r"\b(?:for|to|email)\b", re.IGNORECASE)


class CrmContactRequest(BaseModel):
    """Schema for crm-contact requests."""
    action: str = "list"
    name: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[str] = None
    status: Optional[str] = None


class CrmPipelineRequest(BaseModel):
    """Schema for crm-pipeline requests."""
    action: str = "forecast"
    title: Optional[str] = None
    contact_email: Optional[str] = None
    stage: Optional[str] = None
    value: float = 0.0
    deal_id: Optional[str] = None


SchemaRegistry.register("crm_contact", CrmContactRequest)
SchemaRegistry.register("crm_pipeline", CrmPipelineRequest)


def _parse(query: str, keys: Dict[str, tuple]) -> Dict[str, Any]:
    """Pull ``key value`` pairs and an email out of ``query``.

    ``keys`` maps a canonical field name to the tokens that introduce it.
    An email is extracted first wherever it appears. Each value runs until the
    next introducer in :data:`_TERMINATORS`; whatever is left over becomes
    ``_leftover`` (the name or deal title).
    """
    text = query
    found: Dict[str, Any] = {}

    email = _EMAIL_RE.search(text)
    if email:
        found["email"] = email.group(0).lower()
        text = text[: email.start()] + " " + text[email.end():]

    tokens = text.split()
    for field, introducers in keys.items():
        for i, token in enumerate(tokens):
            if token.lower().strip(",;") not in introducers:
                continue
            claimed: list[str] = []
            j = i + 1
            while j < len(tokens) and tokens[j].lower().strip(",;") not in _TERMINATORS:
                claimed.append(tokens[j])
                j += 1
            value = " ".join(claimed).strip(",;")
            if value:
                found[field] = value
            tokens = tokens[:i] + tokens[j:]
            break

    leftovers = _STRIP_LEAD.sub("", " ".join(tokens))
    leftovers = _STRIP_QUERY_LEAD.sub("", leftovers)
    leftovers = _STRIP_CONNECTORS.sub(" ", leftovers)
    leftovers = re.sub(
        r"\bcontacts?\b|\bdeals?\b|\bpipeline\b", " ", leftovers, flags=re.IGNORECASE
    )
    leftovers = re.sub(r"\s+", " ", leftovers).strip(" ,;-")
    if leftovers:
        found["_leftover"] = leftovers
    return found


def _contact_fields(query: str) -> Dict[str, Any]:
    return _parse(
        query,
        {
            "company": ("at", "company"),
            "tags": ("tag", "tags", "tagged"),
            "status": ("status", "state"),
        },
    )


def _pipeline_fields(query: str, is_move: bool = False) -> Dict[str, Any]:
    """Extract pipeline fields.

    ``is_move`` switches the grammar: in ``move deal <id> to <stage>`` the word
    "deal" introduces the id, while in ``create deal <title> ...`` it is only the
    noun naming the object being created and must not swallow the title.
    """
    keys: Dict[str, tuple] = {
        "stage": ("stage", "to"),
        "value": ("value", "worth"),
    }
    if is_move:
        keys["deal_id"] = ("deal",)
    parsed = _parse(query, keys)
    value = parsed.get("value")
    if isinstance(value, str):
        num = _NUMBER_RE.search(value.replace(",", ""))
        parsed["value"] = float(num.group(0)) if num else 0.0
    return parsed


def _action(query: str, create_words, update_words, list_words) -> Optional[str]:
    low = query.lower()
    if any(re.search(rf"\b{w}\b", low) for w in create_words):
        return "create"
    if any(re.search(rf"\b{w}\b", low) for w in update_words):
        return "update"
    if any(re.search(rf"\b{w}\b", low) for w in list_words):
        return "list"
    if "forecast" in low or "weighted" in low:
        return "forecast"
    return None


def handle_crm_contact(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Deterministic crm-contact handler.

    Recognised actions: create / update / search / list. Anything else is a
    structured failure, not a guess.
    """
    logger.info("Handling CRM contact workflow...")
    action = _action(
        query,
        create_words=("add", "create", "new", "register", "record"),
        update_words=("update", "edit", "change", "set"),
        list_words=("list", "show", "search", "find"),
    )
    fields = _contact_fields(query)

    try:
        if action == "create":
            name = fields.get("name") or fields.get("_leftover")
            if not name:
                return {"status": "failed", "reason": "create contact needs a name (e.g. 'create contact Dana Reed email d@x.test')"}
            payload = {
                "action": "create",
                "name": name,
                "email": fields.get("email"),
                "company": fields.get("company"),
                "tags": fields.get("tags"),
                "status": fields.get("status") or "lead",
            }
            validated = SchemaRegistry.validate_and_parse("crm_contact", payload)
            from tools.crm import get_crm_store

            contact = get_crm_store().contact_action(
                action="create",
                name=validated.name,
                email=validated.email,
                company=validated.company,
                tags=validated.tags,
                status=validated.status or "lead",
            )
            return {"status": "success", "action_taken": "crm_contact_create",
                    "contact": contact["contact"], "crm": contact["contact"]}

        if action == "update":
            if not (fields.get("email") or fields.get("name")):
                return {"status": "failed", "reason": "update contact needs an email or name to match"}
            payload = {
                "action": "update",
                "email": fields.get("email"),
                "name": fields.get("name"),
                "company": fields.get("company"),
                "tags": fields.get("tags"),
                "status": fields.get("status"),
            }
            validated = SchemaRegistry.validate_and_parse("crm_contact", payload)
            from tools.crm import get_crm_store

            patch = {k: v for k, v in {
                "company": validated.company,
                "tags": validated.tags,
                "status": validated.status,
            }.items() if v}
            if not patch:
                return {"status": "failed", "reason": "update contact needs at least one field to change"}
            result = get_crm_store().contact_action(action="update", email=validated.email, fields=patch)
            if not result.get("ok"):
                return {"status": "failed", "reason": result.get("error")}
            return {"status": "success", "action_taken": "crm_contact_update", "contact": result["contact"]}

        if action == "list":
            from tools.crm import get_crm_store

            is_search = ("search" in query.lower() or "find" in query.lower()) and fields
            result = get_crm_store().contact_action(
                action="search" if is_search else "list",
                tags=fields.get("tags"),
                status=fields.get("status"),
                company=fields.get("company"),
            )
            return {
                "status": "success",
                "action_taken": f"crm_contact_{'search' if is_search else 'list'}",
                "count": result["count"],
                "contacts": result["contacts"],
            }

        return {"status": "failed", "reason": f"could not determine a CRM contact action from {query!r}"}

    except ValueError as e:
        logger.error("CRM contact validation failed: %s", e)
        return {"status": "failed", "reason": str(e)}


def handle_crm_pipeline(query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Deterministic crm-pipeline handler.

    Recognised actions: create / move / forecast / list.
    """
    logger.info("Handling CRM pipeline workflow...")
    action = _action(
        query,
        create_words=("add", "create", "new", "register"),
        update_words=("move", "update", "advance", "change"),
        list_words=("list", "show"),
    )
    fields = _pipeline_fields(query, is_move=(action == "update"))

    try:
        if action == "create":
            title = fields.get("title") or fields.get("_leftover")
            if not title:
                return {"status": "failed", "reason": "create deal needs a title (e.g. 'create deal Acme pilot for d@x.test value 12000')"}
            payload = {
                "action": "create",
                "title": title,
                "contact_email": fields.get("email"),
                "stage": fields.get("stage") or "lead",
                "value": fields.get("value") or 0.0,
            }
            validated = SchemaRegistry.validate_and_parse("crm_pipeline", payload)
            from tools.crm import get_crm_store

            deal = get_crm_store().pipeline_action(
                action="create",
                title=validated.title,
                contact_email=validated.contact_email,
                stage=validated.stage or "lead",
                value=validated.value or 0.0,
            )
            return {"status": "success", "action_taken": "crm_deal_create", "deal": deal["deal"]}

        if action == "update":
            deal_id = fields.get("deal_id")
            stage = fields.get("stage")
            if not deal_id or not stage:
                return {"status": "failed", "reason": "move deal needs 'deal <id>' and a 'stage <stage>'"}
            from tools.crm import get_crm_store

            result = get_crm_store().pipeline_action(action="move", deal_id=deal_id, stage=stage)
            if not result.get("ok"):
                return {"status": "failed", "reason": result.get("error")}
            return {"status": "success", "action_taken": "crm_deal_move", "deal": result["deal"]}

        if action in ("list", "forecast") or "forecast" in query.lower():
            from tools.crm import get_crm_store

            store = get_crm_store()
            if action == "forecast" or "forecast" in query.lower():
                result = store.pipeline_action(action="forecast")
                return {"status": "success", "action_taken": "crm_forecast", "forecast": result["forecast"]}
            result = store.pipeline_action(action="list", stage=fields.get("stage"))
            return {"status": "success", "action_taken": "crm_deal_list",
                    "count": result["count"], "deals": result["deals"]}

        return {"status": "failed", "reason": f"could not determine a CRM pipeline action from {query!r}"}

    except ValueError as e:
        logger.error("CRM pipeline validation failed: %s", e)
        return {"status": "failed", "reason": str(e)}


def register_crm_tools_skill(intent_router: IntentRouter) -> None:
    """Register the CRM contact and pipeline intents.

    Keywords mirror ``swarm.yaml``'s ``crm-contact`` / ``crm-pipeline`` entries
    so a routed query and a swarm route name resolve to the same handler.

    Registered *after* the content skills on purpose: ``IntentRouter`` returns
    the first intent whose keyword matches, and a query naming both ("write a
    blog post about CRM") should reach the content engine — which knows how to
    aim copy at a CRM segment — rather than the CRM write path.
    """
    intent_router.register_intent(
        intent_name="crm_contact",
        keywords=[
            "contact management", "customer", "lead", "contact list", "CRM",
            "add contact", "create contact", "update contact", "search contacts",
            "list contacts", "show contacts", "crm contact",
        ],
        handler=handle_crm_contact,
    )
    intent_router.register_intent(
        intent_name="crm_pipeline",
        keywords=[
            "sales pipeline", "deal flow", "opportunity", "stages", "forecast",
            "create deal", "move deal", "pipeline forecast", "crm pipeline",
            "list deals", "show deals",
        ],
        handler=handle_crm_pipeline,
    )
    logger.info("CRM contact + pipeline skills wrapped and registered.")

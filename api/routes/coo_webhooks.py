"""COO Brain webhook ingestion routes — Sentry, GitHub, Stripe webhooks."""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from coo.orchestrator import get_orchestrator
from coo.state import DecisionCard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coo", tags=["coo-brain"])


def _verify_github_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return True  # Skip verification if no secret configured
    expected = f"sha256={hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}"
    return hmac.compare_digest(signature, expected)


def _verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    """Verify Stripe webhook signature (simplified — no timestamp tolerance check)."""
    secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return True  # Skip verification if no secret configured
    try:
        parts = dict(item.split("=") for item in sig_header.split(","))
        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


class WebhookResponse(BaseModel):
    status: str
    zone: str = ""
    event_id: str = ""
    issue_number: Optional[int] = None
    message: str = ""


class DecisionCardResponse(BaseModel):
    event_id: str
    product_id: str
    zone: str
    summary: str
    diagnosis: str
    proposed_fix: str
    github_issue_number: Optional[int] = None
    resolved: bool = False
    outcome: Optional[str] = None


@router.post("/webhook/sentry", response_model=WebhookResponse)
async def sentry_webhook(request: Request):
    """Ingest Sentry exception webhooks with security check."""
    # Basic security: Check for Sentry-specific header if configured
    sentry_token = os.getenv("SENTRY_WEBHOOK_TOKEN", "")
    if sentry_token:
        provided = request.headers.get("Sentry-Hook-Signature", "")
        if not provided:
            logger.warning("Sentry webhook missing signature")
            raise HTTPException(status_code=401, detail="Missing signature")
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    product_id = body.get("product_id", "unknown")
    # Validate product is in our portfolio
    orchestrator = get_orchestrator()
    if product_id != "unknown" and product_id not in orchestrator.portfolio.products:
        logger.warning("Sentry event for unknown product: %s", product_id)
        return WebhookResponse(status="skipped", message="Product not in portfolio")

    event_type = body.get("event_type", "exception")
    severity = float(body.get("severity", 0.0))
    error_msg = body.get("message", body.get("error_message", ""))

    raw_event = {
        "event_type": event_type,
        "product_id": product_id,
        "severity": severity,
        "error_message": error_msg,
        "summary": body.get("summary", f"Sentry: {error_msg[:80]}"),
        "details": body,
    }

    orchestrator = get_orchestrator()
    card = orchestrator.process_event(raw_event)
    if card is None:
        return WebhookResponse(status="skipped", message="Unknown product")

    return WebhookResponse(
        status="processed",
        zone=card.zone.value,
        event_id=card.event_id,
        issue_number=card.github_issue_number,
        message=f"Event classified as {card.zone.value}",
    )


@router.post("/webhook/github", response_model=WebhookResponse)
async def github_webhook(request: Request):
    """Ingest GitHub webhooks (CI failures, PR events, issue closures)."""
    body_bytes = await request.body()
    sig_header = request.headers.get("X-Hub-Signature-256", "")
    if sig_header and not _verify_github_signature(body_bytes, sig_header):
        logger.warning("GitHub webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = body.get("action", "")
    event_type = body.get("event_type", "")

    # Handle issue closure — this is the human approval signal
    if action == "closed" and "issue" in body:
        issue_number = body["issue"].get("number")
        if issue_number:
            orchestrator = get_orchestrator()
            resolved = orchestrator.handle_issue_closed(issue_number, outcome="approved")
            return WebhookResponse(
                status="resolved" if resolved else "not_found",
                message=f"Issue #{issue_number} closed {'and resolved' if resolved else '(no matching card)'}",
            )

    # Handle CI failure
    if event_type == "ci_failure" or action == "failure":
        repo = body.get("repository", {}).get("name", "unknown")
        raw_event = {
            "event_type": "build_failure",
            "product_id": repo,
            "severity": 0.3,
            "error_message": body.get("message", "CI pipeline failed"),
            "summary": f"CI failure in {repo}",
            "details": body,
        }
        orchestrator = get_orchestrator()
        card = orchestrator.process_event(raw_event)
        if card:
            return WebhookResponse(
                status="processed",
                zone=card.zone.value,
                event_id=card.event_id,
                issue_number=card.github_issue_number,
                message=f"CI failure classified as {card.zone.value}",
            )

    return WebhookResponse(status="ignored", message="No action required")


@router.post("/webhook/stripe", response_model=WebhookResponse)
async def stripe_webhook(request: Request):
    """Ingest Stripe webhooks (subscription changes, payment failures)."""
    body_bytes = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    if sig_header and not _verify_stripe_signature(body_bytes, sig_header):
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = body.get("type", "")
    product_id = body.get("product_id", "unknown")

    if "invoice.payment_failed" in event_type:
        raw_event = {
            "event_type": "stripe_payment_failed",
            "product_id": product_id,
            "severity": 0.5,
            "error_message": f"Stripe payment failed: {event_type}",
            "summary": f"Payment failure — {event_type}",
            "details": body,
        }
        orchestrator = get_orchestrator()
        card = orchestrator.process_event(raw_event)
        if card:
            return WebhookResponse(
                status="processed",
                zone=card.zone.value,
                event_id=card.event_id,
                issue_number=card.github_issue_number,
                message=f"Payment failure classified as {card.zone.value}",
            )

    if "customer.subscription.deleted" in event_type:
        raw_event = {
            "event_type": "stripe_subscription_canceled",
            "product_id": product_id,
            "severity": 0.7,
            "error_message": f"Subscription canceled: {event_type}",
            "summary": f"Subscription canceled — {event_type}",
            "details": body,
        }
        orchestrator = get_orchestrator()
        card = orchestrator.process_event(raw_event)
        if card:
            return WebhookResponse(
                status="processed",
                zone=card.zone.value,
                event_id=card.event_id,
                issue_number=card.github_issue_number,
                message=f"Subscription cancellation classified as {card.zone.value}",
            )

    return WebhookResponse(status="ignored", message=f"No handler for {event_type}")


@router.get("/status")
async def get_status():
    """Get COO Brain operational status."""
    orchestrator = get_orchestrator()
    status = orchestrator.get_status()
    return {
        "status": "operational",
        "coo_brain": status,
        "products_registered": len(status["products"]),
    }


@router.get("/decisions/pending", response_model=List[DecisionCardResponse])
async def get_pending_decisions():
    """Get all pending (unresolved) decision cards."""
    orchestrator = get_orchestrator()
    decisions = orchestrator.get_pending_decisions()
    return [
        DecisionCardResponse(
            event_id=d.event_id,
            product_id=d.product_id,
            zone=d.zone.value,
            summary=d.summary,
            diagnosis=d.diagnosis,
            proposed_fix=d.proposed_fix,
            github_issue_number=d.github_issue_number,
            resolved=d.resolved,
            outcome=d.outcome,
        )
        for d in decisions
    ]


@router.get("/decisions/log", response_model=List[DecisionCardResponse])
async def get_decision_log():
    """Get the full decision log."""
    orchestrator = get_orchestrator()
    decisions = orchestrator.get_decision_log()
    return [
        DecisionCardResponse(
            event_id=d.event_id,
            product_id=d.product_id,
            zone=d.zone.value,
            summary=d.summary,
            diagnosis=d.diagnosis,
            proposed_fix=d.proposed_fix,
            github_issue_number=d.github_issue_number,
            resolved=d.resolved,
            outcome=d.outcome,
        )
        for d in decisions
    ]


@router.post("/decisions/{issue_number}/resolve", response_model=WebhookResponse)
async def resolve_decision(issue_number: int, outcome: str = "approved"):
    """Manually resolve a decision card by issue number."""
    orchestrator = get_orchestrator()
    resolved = orchestrator.handle_issue_closed(issue_number, outcome=outcome)
    if resolved:
        return WebhookResponse(
            status="resolved",
            message=f"Issue #{issue_number} resolved with outcome '{outcome}'",
        )
    return WebhookResponse(status="not_found", message=f"No decision card for issue #{issue_number}")

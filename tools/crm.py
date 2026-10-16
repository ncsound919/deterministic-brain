"""CRM tools — deterministic contacts and deal pipeline over JSON stores.

The brain's ``crm-contact``, ``crm-pipeline`` and ``content-schedule`` skill
packs (``skill_packs/business/*/skill.md``) declare ``file_read`` /
``file_write`` against ``crm/contacts.json``, ``crm/pipeline.json``,
``content/calendar.json`` and ``content/activity.json``. Those store files
exist on disk and are empty, and nothing in the tree ever read or wrote them:
``LocalSkillBackend`` cannot execute a prose skill.md at all (it only renders
Jinja templates), so every CRM query fell through to the LLM fallback and
failed with ``"No LLM API key configured"``.

This module is the deterministic implementation of that specification. It is
the seam the content engine reads audience segments from, and the write-back
path the marketing engine records marketing touches on.

Timestamps are canonical ``YYYY-MM-DDTHH:MM:SSZ`` and are validated at write
time with :func:`is_iso_utc`, so a lexicographic comparison of two stored
values is always a chronological one — see
``Coding lessons/2026-10-12-oss-crm-lexical-timestamps-need-format-guards.md``.

Store layout (all paths overridable via ``BRAIN_CRM_DIR``)::

    crm/contacts.json     {"contacts": [...]}
    crm/pipeline.json     {"deals": [...]}
    crm/activities.json   {"activities": [...]}
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BRAIN_ROOT = Path(__file__).resolve().parents[1]

#: Canonical pipeline stages, in order. Mirrors ``crm-pipeline`` skill.md:
#: lead -> qualified -> proposal -> closed.
STAGES: tuple[str, ...] = ("lead", "qualified", "proposal", "closed")

#: Stages that are still open. A closed deal is terminal in either direction;
#: this store does not model won/lost separately.
OPEN_STAGES: tuple[str, ...] = ("lead", "qualified", "proposal")

#: Fixed per-stage win probability. Deterministic policy, not model output —
#: the weighted forecast is only meaningful if every reader uses the same weights.
STAGE_PROBABILITY: Dict[str, float] = {
    "lead": 0.10,
    "qualified": 0.25,
    "proposal": 0.50,
    "closed": 1.00,
}

_ISO_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_SPLIT_RE = re.compile(r"[,\s]+")


def is_iso_utc(value: Any) -> bool:
    """True when ``value`` is a canonical ``YYYY-MM-DDTHH:MM:SSZ`` string.

    A bare ``isoformat()`` from an offset-aware or microsecond-carrying
    datetime still *looks* ISO-8601 but breaks every lexicographic comparison.
    This is the write-time guard.
    """
    return isinstance(value, str) and bool(_ISO_UTC_RE.fullmatch(value))


def utcnow() -> str:
    """Canonical UTC timestamp, safe to compare lexicographically."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def crm_dir() -> Path:
    """Directory holding the CRM JSON stores."""
    return Path(os.getenv("BRAIN_CRM_DIR") or (_BRAIN_ROOT / "crm"))


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


class CRMError(ValueError):
    """Raised for a rejected CRM operation (bad stage, missing field, ...)."""


def _normalise_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [t.strip() for t in _SPLIT_RE.split(value) if t.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(t).strip() for t in value if str(t).strip()]
    raise CRMError(f"tags must be a string or list, got {type(value).__name__}")


def _clean(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _require(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CRMError(f"{field} is required")
    return value.strip()


class CRMStore:
    """Contacts + deal pipeline + activities, persisted as JSON.

    Every mutation is written atomically (temp file + ``os.replace``) so a
    crash mid-write cannot truncate a store. An unreadable store file is
    reported and left on disk — it is only ever replaced by the next
    *successful* mutation, never by a read.
    """

    def __init__(self, root: Optional[str | os.PathLike] = None):
        self.root = Path(root) if root else crm_dir()
        self.contacts_path = self.root / "contacts.json"
        self.pipeline_path = self.root / "pipeline.json"
        self.activities_path = self.root / "activities.json"
        self.contacts: List[Dict[str, Any]] = self._load(self.contacts_path, "contacts")
        self.deals: List[Dict[str, Any]] = self._load(self.pipeline_path, "deals")
        self.activities: List[Dict[str, Any]] = self._load(self.activities_path, "activities")

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _load(self, path: Path, key: str) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            logger.warning("CRM store %s is unreadable (%s) — empty view, file left on disk", path, exc)
            return []
        rows = data.get(key) if isinstance(data, dict) else None
        if not isinstance(rows, list):
            logger.warning("CRM store %s has no %r list — empty view", path, key)
            return []
        return [r for r in rows if isinstance(r, dict)]

    def _save(self, path: Path, key: str, rows: List[Dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps({key: rows}, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    def _save_contacts(self) -> None:
        self._save(self.contacts_path, "contacts", self.contacts)

    def _save_deals(self) -> None:
        self._save(self.pipeline_path, "deals", self.deals)

    def _save_activities(self) -> None:
        self._save(self.activities_path, "activities", self.activities)

    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    def create_contact(
        self,
        name: str,
        email: Optional[str] = None,
        company: Optional[str] = None,
        tags: Any = None,
        status: str = "lead",
        title: Optional[str] = None,
        phone: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a contact. ``email`` is the natural key when present."""
        created = utcnow()
        contact = {
            "id": _short_id(),
            "name": _require(name, "name"),
            "email": _clean(email),
            "company": _clean(company),
            "title": _clean(title),
            "phone": _clean(phone),
            "source": _clean(source),
            "tags": _normalise_tags(tags),
            "status": status,
            "created_at": created,
            "updated_at": created,
            "last_contacted_at": None,
        }
        self.contacts.append(contact)
        self._save_contacts()
        return dict(contact)

    def find_contact(
        self, email: Optional[str] = None, contact_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if email:
            needle = email.strip().lower()
            for c in self.contacts:
                if (c.get("email") or "").lower() == needle:
                    return c
        if contact_id:
            for c in self.contacts:
                if c.get("id") == contact_id:
                    return c
        return None

    def update_contact(
        self,
        email: Optional[str] = None,
        contact_id: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        """Update a contact found by ``email`` or ``contact_id``.

        Field names follow ``create_contact`` (``company``, ``tags``, ...) so
        the same vocabulary works in both directions. Returns ``None`` when no
        contact matches.
        """
        contact = self.find_contact(email=email, contact_id=contact_id)
        if contact is None:
            return None
        patch: Dict[str, Any] = {**(fields or {}), **kwargs}
        if "tags" in patch:
            patch["tags"] = _normalise_tags(patch["tags"])
        for field in ("name", "email", "company", "title", "phone", "source", "status"):
            if field in patch and isinstance(patch[field], str):
                patch[field] = _clean(patch[field])
        if "name" in patch and not patch["name"]:
            raise CRMError("name cannot be empty")
        contact.update({k: v for k, v in patch.items() if v is not None or k in ("tags",)})
        contact["updated_at"] = utcnow()
        self._save_contacts()
        return dict(contact)

    def search_contacts(
        self,
        query: Optional[str] = None,
        tags: Any = None,
        status: Optional[str] = None,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter contacts by free text, tag(s), status and/or company.

        Multiple tags are ANDed; the free-text ``query`` matches name, email,
        company, title, source and tags.
        """
        wanted = [t.lower() for t in _normalise_tags(tags)]
        needle = (query or "").strip().lower()
        out: List[Dict[str, Any]] = []
        for c in self.contacts:
            if status and c.get("status") != status:
                continue
            if company and (c.get("company") or "").lower() != company.strip().lower():
                continue
            held = [str(t).lower() for t in (c.get("tags") or [])]
            if wanted and not all(t in held for t in wanted):
                continue
            if needle:
                fields = " ".join(
                    str(c.get(f) or "") for f in ("name", "email", "company", "title", "source")
                ).lower()
                if needle not in fields and needle not in " ".join(held):
                    continue
            out.append(dict(c))
        return out

    def list_contacts(self) -> List[Dict[str, Any]]:
        """All contacts, most recently updated first."""
        return [
            dict(c)
            for c in sorted(self.contacts, key=lambda c: c.get("updated_at", ""), reverse=True)
        ]

    def mark_contacted(self, contact_id: str, at: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Stamp ``last_contacted_at`` on a contact (validated, canonical)."""
        contact = self.find_contact(contact_id=contact_id)
        if contact is None:
            return None
        stamp = at or utcnow()
        if not is_iso_utc(stamp):
            raise CRMError(f"last_contacted_at must be canonical ISO-8601 UTC, got {stamp!r}")
        contact["last_contacted_at"] = stamp
        contact["updated_at"] = utcnow()
        self._save_contacts()
        return dict(contact)

    # ------------------------------------------------------------------
    # deals
    # ------------------------------------------------------------------
    def create_deal(
        self,
        title: str,
        contact_email: Optional[str] = None,
        stage: str = "lead",
        value: float = 0.0,
        currency: str = "USD",
        source: Optional[str] = None,
        expected_close: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a deal. ``contact_email`` is resolved to a contact id when present."""
        if stage not in STAGES:
            raise CRMError(f"stage must be one of {', '.join(STAGES)} (got {stage!r})")
        if expected_close is not None and not is_iso_utc(expected_close):
            raise CRMError(f"expected_close must be canonical ISO-8601 UTC, got {expected_close!r}")
        created = utcnow()
        contact = self.find_contact(email=contact_email) if contact_email else None
        deal = {
            "id": _short_id(),
            "title": _require(title, "title"),
            "contact_id": contact.get("id") if contact else None,
            "contact_email": contact.get("email") if contact else _clean(contact_email),
            "stage": stage,
            "value": float(value or 0.0),
            "currency": currency or "USD",
            "probability": STAGE_PROBABILITY[stage],
            "source": _clean(source),
            "expected_close": expected_close,
            "created_at": created,
            "updated_at": created,
            "closed_at": created if stage == "closed" else None,
        }
        self.deals.append(deal)
        self._save_deals()
        return dict(deal)

    def find_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        for d in self.deals:
            if d.get("id") == deal_id:
                return d
        return None

    def move_deal(self, deal_id: str, stage: str) -> Optional[Dict[str, Any]]:
        """Move a deal to ``stage``, re-deriving its win probability."""
        if stage not in STAGES:
            raise CRMError(f"stage must be one of {', '.join(STAGES)} (got {stage!r})")
        deal = self.find_deal(deal_id)
        if deal is None:
            return None
        now = utcnow()
        deal["stage"] = stage
        deal["probability"] = STAGE_PROBABILITY[stage]
        deal["updated_at"] = now
        deal["closed_at"] = now if stage == "closed" else None
        self._save_deals()
        return dict(deal)

    def list_deals(self, stage: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self.deals if not stage else [d for d in self.deals if d.get("stage") == stage]
        return [dict(d) for d in sorted(rows, key=lambda d: d.get("updated_at", ""), reverse=True)]

    def open_deals(self) -> List[Dict[str, Any]]:
        """Deals that are not closed, in stage order then by value."""
        rows = [d for d in self.deals if d.get("stage") in OPEN_STAGES]
        return [
            dict(d)
            for d in sorted(
                rows,
                key=lambda d: (STAGES.index(d.get("stage", "lead")), -float(d.get("value") or 0.0)),
            )
        ]

    def forecast(self) -> Dict[str, Any]:
        """Sum value by stage and compute the weighted pipeline.

        ``total`` is the unweighted value of open deals; ``weighted`` applies
        :data:`STAGE_PROBABILITY` and is the only number comparable across
        readers.
        """
        by_stage: Dict[str, Dict[str, float]] = {
            s: {"count": 0, "value": 0.0, "weighted_value": 0.0} for s in STAGES
        }
        for d in self.deals:
            stage = d.get("stage", "lead")
            if stage not in by_stage:
                continue
            value = float(d.get("value") or 0.0)
            by_stage[stage]["count"] += 1
            by_stage[stage]["value"] += value
            by_stage[stage]["weighted_value"] += value * STAGE_PROBABILITY[stage]
        open_value = sum(by_stage[s]["value"] for s in OPEN_STAGES)
        weighted = sum(by_stage[s]["weighted_value"] for s in OPEN_STAGES)
        closed_value = by_stage["closed"]["value"]
        return {
            "currency": self.deals[0].get("currency", "USD") if self.deals else "USD",
            "total_open_value": round(open_value, 2),
            "weighted_open_value": round(weighted, 2),
            "closed_value": round(closed_value, 2),
            "open_deal_count": sum(by_stage[s]["count"] for s in OPEN_STAGES),
            "by_stage": by_stage,
        }

    # ------------------------------------------------------------------
    # activities
    # ------------------------------------------------------------------
    def log_activity(
        self,
        subject_type: str,
        subject_id: str,
        kind: str,
        note: Optional[str] = None,
        due_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an activity against a contact or a deal."""
        if subject_type not in ("contact", "deal"):
            raise CRMError(f"subject_type must be 'contact' or 'deal' (got {subject_type!r})")
        if due_at is not None and not is_iso_utc(due_at):
            raise CRMError(f"due_at must be canonical ISO-8601 UTC, got {due_at!r}")
        activity = {
            "id": _short_id(),
            "subject_type": subject_type,
            "subject_id": _require(subject_id, "subject_id"),
            "kind": _require(kind, "kind"),
            "note": _clean(note),
            "due_at": due_at,
            "done_at": None,
            "created_at": utcnow(),
        }
        self.activities.append(activity)
        self._save_activities()
        return dict(activity)

    def list_activities(
        self, subject_type: Optional[str] = None, subject_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        rows = self.activities
        if subject_type:
            rows = [a for a in rows if a.get("subject_type") == subject_type]
        if subject_id:
            rows = [a for a in rows if a.get("subject_id") == subject_id]
        return [dict(a) for a in sorted(rows, key=lambda a: a.get("created_at", ""), reverse=True)]

    # ------------------------------------------------------------------
    # action dispatch — the ToolRegistry surface (crm_contact / crm_pipeline)
    # ------------------------------------------------------------------
    def contact_action(self, action: str = "list", **kw: Any) -> Dict[str, Any]:
        """Single entry point for the ``crm-contact`` skill pack.

        ``action`` is one of ``create`` / ``update`` / ``search`` / ``list``,
        matching the skill's Step 2 vocabulary. Everything else is rejected
        rather than silently ignored — an unrecognised action must not look
        like a completed one.
        """
        if action == "create":
            return {"ok": True, "action": "create", "contact": self.create_contact(**kw)}
        if action == "update":
            updated = self.update_contact(**kw)
            if updated is None:
                return {"ok": False, "action": "update", "error": "no contact matches the given email/id"}
            return {"ok": True, "action": "update", "contact": updated}
        if action == "search":
            contacts = self.search_contacts(**kw)
            return {"ok": True, "action": "search", "count": len(contacts), "contacts": contacts}
        if action == "list":
            contacts = self.list_contacts()
            return {"ok": True, "action": "list", "count": len(contacts), "contacts": contacts}
        raise CRMError(f"unknown contact action {action!r} (expected create, update, search, list)")

    def pipeline_action(self, action: str = "forecast", **kw: Any) -> Dict[str, Any]:
        """Single entry point for the ``crm-pipeline`` skill pack.

        ``action`` is one of ``create`` / ``move`` / ``forecast``.
        """
        if action == "create":
            return {"ok": True, "action": "create", "deal": self.create_deal(**kw)}
        if action == "move":
            moved = self.move_deal(**kw)
            if moved is None:
                return {"ok": False, "action": "move", "error": "no deal with that id"}
            return {"ok": True, "action": "move", "deal": moved}
        if action == "forecast":
            return {"ok": True, "action": "forecast", "forecast": self.forecast()}
        if action == "list":
            deals = self.list_deals(**kw)
            return {"ok": True, "action": "list", "count": len(deals), "deals": deals}
        raise CRMError(f"unknown pipeline action {action!r} (expected create, move, forecast, list)")

    # ------------------------------------------------------------------
    # segments — the content engine's audience source
    # ------------------------------------------------------------------
    def audience_segments(self) -> List[Dict[str, Any]]:
        """Deterministic audience roll-up keyed by tag, then company.

        Each segment carries the tag (or company name), the contacts in it and
        the open deals attached to them — the inputs the content engine needs
        to aim copy at a real audience rather than a guess.
        """
        segments: Dict[str, Dict[str, Any]] = {}

        def _bucket(field: str, value: str) -> Dict[str, Any]:
            k = f"{field}:{value.lower()}"
            return segments.setdefault(
                k, {"segment": value, "field": field, "contacts": [], "open_deals": [], "open_value": 0.0}
            )

        for c in self.contacts:
            for tag in c.get("tags") or []:
                _bucket("tag", str(tag))["contacts"].append(c)
            if c.get("company"):
                _bucket("company", c["company"])["contacts"].append(c)

        contact_ids = {c.get("id") for c in self.contacts}
        for deal in self.open_deals():
            cid = deal.get("contact_id")
            if cid not in contact_ids:
                continue
            contact = next((c for c in self.contacts if c.get("id") == cid), None)
            if not contact:
                continue
            for tag in contact.get("tags") or []:
                _bucket("tag", str(tag))["open_deals"].append(deal)
            if contact.get("company"):
                _bucket("company", contact["company"])["open_deals"].append(deal)

        out: List[Dict[str, Any]] = []
        for seg in segments.values():
            contacts = seg.pop("contacts")
            deals = seg.pop("open_deals")
            seg["contact_count"] = len(contacts)
            seg["open_deal_count"] = len(deals)
            seg["open_value"] = round(sum(float(d.get("value") or 0.0) for d in deals), 2)
            seg["contact_ids"] = [c.get("id") for c in contacts]
            out.append(seg)
        # Most valuable audience first; ties broken by contact count then name.
        return sorted(
            out,
            key=lambda s: (-s["open_value"], -s["contact_count"], str(s["segment"]).lower()),
        )


_STORE: Optional[CRMStore] = None


def get_crm_store() -> CRMStore:
    """Process-wide CRM store (single reader/writer over the JSON files)."""
    global _STORE
    if _STORE is None:
        _STORE = CRMStore()
    return _STORE


def reset_store() -> None:
    """Drop the cached store — used by tests to pick up a new ``BRAIN_CRM_DIR``."""
    global _STORE
    _STORE = None

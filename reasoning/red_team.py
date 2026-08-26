"""Dev Brain — adversarial red-team stress engine.

Ported from ncsound919/Dev-Brain src/engine/redTeamEngine.ts.
Evaluates a decision against 4 deterministic adversarial stress vectors:
competitor counter-strike, black-swan infra shock, cascading operational
friction, and regulatory shift.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

_THREAT_WEIGHTS = {"CRITICAL": 1.0, "SEVERE": 0.75, "MODERATE": 0.45}

_FORTIFICATIONS = [
    "Establish automated circuit breakers that sever dependencies before "
    "cascading buffer saturation.",
    "Adopt dual-sourcing across all external APIs and mission-critical "
    "software vendors.",
    "Run monthly chaos red-team game days simulating black-swan partitioned "
    "state failures.",
    "Embed immutable cryptographically auditable event logs to defeat "
    "regulatory disputes.",
]


class AdversarialRedTeamEngine:
    def run_simulation(
        self,
        decision_title: str,
        evaluated_option: str,
        domain_hint: str = "",
        seed: int = 0,
    ) -> Dict[str, Any]:
        lower = f"{decision_title} {evaluated_option} {domain_hint}".lower()
        scenarios: List[Dict[str, Any]] = []

        # 1. Adversary counter-strike (sector-aware)
        if any(k in lower for k in (
                "kafka", "database", "cloud", "infra", "dev")):
            counter = {
                "name": "Zero-Day Dependency Exploit & Vendor Price Gouging",
                "attackVector": (
                    "Critical CVE discovered in open-source ingestion runtime "
                    "combined with 300% storage tier price hike."
                ),
                "failureMode": (
                    "Emergency hot-patching causing 4 hours of cascading "
                    "cluster downtime and SLA penalties."
                ),
                "counterMitigation": (
                    "Implement multi-AZ failover cluster with automated "
                    "hermetic image rollback pipelines."
                ),
                "threatLevel": "SEVERE", "probability": 45, "impactScore": 8,
            }
        elif any(k in lower for k in (
                "car-t", "bio", "tumor", "clinical")):
            counter = {
                "name": "Hostile Patent Encirclement & Cell Therapy "
                        "Off-Target Lawsuit",
                "attackVector": (
                    "Competitor files blocking composition-of-matter patent "
                    "claims on hinge/transmembrane domain."
                ),
                "failureMode": (
                    "Indefinite FDA clinical hold pending freedom-to-operate "
                    "litigation."
                ),
                "counterMitigation": (
                    "Design orthogonal synthetic receptor variants and file "
                    "expedited utility patents across 4 continents."
                ),
                "threatLevel": "CRITICAL", "probability": 35, "impactScore": 9,
            }
        elif any(k in lower for k in (
                "speed", "injury", "sports", "fatigue")):
            counter = {
                "name": "Opponent High-Pressing CNS Overload Trap",
                "attackVector": (
                    "Opposing coaching staff intentionally dictates "
                    "120-possession game pace to exploit biomechanical "
                    "fatigue."
                ),
                "failureMode": (
                    "Fourth-quarter deceleration decay leading to acute "
                    "muscle strain and blown lead."
                ),
                "counterMitigation": (
                    "Strict 28-minute rotational hard-cap and targeted "
                    "isotonic electrolyte recovery intervals."
                ),
                "threatLevel": "MODERATE", "probability": 75, "impactScore": 6,
            }
        else:
            counter = {
                "name": "Competitor Price War & Feature Copycat Strike",
                "attackVector": (
                    "Rival releases a cloned architecture within 6 weeks, "
                    "subsidized by VC/parent cash flow."
                ),
                "failureMode": (
                    "Margin compression and customer hesitation during "
                    "procurement cycle."
                ),
                "counterMitigation": (
                    "Erect proprietary data flywheel and lock-in switching "
                    "barriers via workflow integrations."
                ),
                "threatLevel": "MODERATE", "probability": 65, "impactScore": 7,
            }
        counter.update({
            "id": f"sc-adv-{seed or int(time.time() * 1000)}-1",
            "type": "adversary_counter",
            "blastRadius": "Direct Revenue & Operational SLA (Zone 1)",
            "preMortemTrigger": (
                "If competitor launches equivalent within 60 days, activate "
                "Tier-2 differentiation playbook immediately."
            ),
        })
        scenarios.append(counter)

        # 2. Black-swan macro shock
        scenarios.append({
            "id": f"sc-bs-{seed or int(time.time() * 1000)}-2",
            "name": ("Black Swan: Regional Infrastructure Blackout & Cloud "
                     "API Severance"),
            "type": "black_swan",
            "threatLevel": "SEVERE",
            "probability": 18,
            "impactScore": 9,
            "attackVector": (
                "Primary cloud data center suffers undersea cable cut and DNS "
                "routing table corruption."
            ),
            "failureMode": (
                "Data partition split-brain condition where asynchronous "
                "nodes accept divergent writes."
            ),
            "blastRadius": "Global Ingestion Mesh & Consistency Guarantees (Zone 3)",
            "counterMitigation": (
                "Enforce strict CRDT deterministic merge resolution and "
                "offline-first local state queues."
            ),
            "preMortemTrigger": (
                "Heartbeat latency > 1200ms triggers automatic read-only "
                "quarantine and replica failover."
            ),
        })

        # 3. Cascading operational friction
        scenarios.append({
            "id": f"sc-casc-{seed or int(time.time() * 1000)}-3",
            "name": ("Cascading System Friction: Silent Memory Degradation & "
                     "Skill Attrition"),
            "type": "cascade_friction",
            "threatLevel": "MODERATE",
            "probability": 55,
            "impactScore": 6,
            "attackVector": (
                "Core architect departures combined with unprofiled GC pause "
                "drift in production."
            ),
            "failureMode": (
                "Mean Time to Resolution (MTTR) increases from 12 minutes to "
                "5.5 hours over 6 months."
            ),
            "blastRadius": "Engineering Team Velocity & On-Call Burnout (Zone 2)",
            "counterMitigation": (
                "Implement executable architecture decision records (ADRs) "
                "and deterministic FSM guardrails."
            ),
            "preMortemTrigger": (
                "MTTR exceeding 45 minutes triggers mandatory 2-week "
                "architectural refactoring sprint."
            ),
        })

        # 4. Regulatory / policy shock
        scenarios.append({
            "id": f"sc-reg-{seed or int(time.time() * 1000)}-4",
            "name": ("Regulatory Shock: Instant Sovereignty & Privacy Mandate "
                     "Shift"),
            "type": "regulatory_shock",
            "threatLevel": "MODERATE",
            "probability": 30,
            "impactScore": 8,
            "attackVector": (
                "New international sovereignty directive mandates zero "
                "telemetry export across jurisdictional borders."
            ),
            "failureMode": (
                "Existing analytics pipelines become non-compliant overnight "
                "subject to 4% turnover fines."
            ),
            "blastRadius": "Legal Compliance & Cross-Border Data Ingestion (Zone 4)",
            "counterMitigation": (
                "Architect zero-knowledge edge hashing and self-contained "
                "local inferencing instances."
            ),
            "preMortemTrigger": (
                "Regulatory notice initiates automated localized database "
                "sharding script."
            ),
        })

        threat_sum = sum(
            (s["probability"] / 100)
            * (s["impactScore"] / 10)
            * 35
            * _THREAT_WEIGHTS.get(s["threatLevel"], 0.2)
            for s in scenarios
        )
        resilience = max(15, min(95, round(100 - threat_sum)))
        if resilience < 40:
            grade = "FRAGILE"
        elif resilience < 65:
            grade = "VULNERABLE"
        elif resilience < 80:
            grade = "RESILIENT"
        else:
            grade = "FORTIFIED"

        primary_vulnerability = max(
            scenarios,
            key=lambda s: s["impactScore"] * s["probability"],
        )["name"]

        rid = format(seed or int(time.time() * 1000), "x")
        return {
            "id": f"redteam-{rid}",
            "decisionTitle": decision_title,
            "evaluatedOption": evaluated_option,
            "resilienceScore": resilience,
            "robustnessGrade": grade,
            "simulatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scenarios": scenarios,
            "primaryVulnerability": primary_vulnerability,
            "recommendedFortifications": list(_FORTIFICATIONS),
            "preMortemSummary": (
                f"If this decision fails 12 months from now, it will be due "
                f"to {scenarios[0]['name'].lower()} interacting with "
                f"unmitigated operational friction. Implement the recommended "
                f"circuit breakers immediately."
            ),
            "worstCaseSurvivalProbability": max(
                45, min(98, round(resilience * 0.95 + 8))
            ),
        }

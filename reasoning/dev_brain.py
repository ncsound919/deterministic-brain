"""Dev Brain — deterministic genome-council decision engine.

Ported from ncsound919/Dev-Brain (TypeScript) into the deterministic-brain
reasoning engine set. 100% LLM-free, fully reproducible given the same inputs
(ids embed wall-clock time only for traceability, never for decisions).

Pipeline FSM (mirrors src/engine/reasoningEngine.ts):
    PERCEIVE   ANALYZE_PROBLEM      sector/domain/constraints/complexity
    ROUTE      MATCH_GENOMES        believability-weighted genome ranking
    SYNTHESIZE SYNTHESIZE_SOLUTION  composite synthesis + confidence

Every run returns a fully traceable audit trail with public-source attribution.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "dev_brain_genomes.json"

SECTORS = ("dev", "business", "financial", "science_biotech", "science_sports")

_SECTOR_KEYWORDS: Dict[str, Iterable[str]] = {
    "science_biotech": (
        "cancer", "car-t", "crispr", "genom", "t-cell", "biotech",
    ),
    "science_sports": (
        "hypertrophy", "spine", "vo2", "sprint", "acwr", "workout", "mobility",
    ),
    "financial": (
        "valuation", "dcf", "margin of safety", "fpa", "cash flow", "ebitda",
        "investing",
    ),
    "business": (
        "disruption", "jtbd", "strategy", "flywheel", "okr", "culture",
        "business model",
    ),
}

_DOMAIN_KEYWORDS: Dict[str, Iterable[str]] = {
    "architecture": (
        "design", "system", "structure", "framework", "distributed", "pipeline",
    ),
    "optimization": (
        "fast", "efficient", "speed", "performance", "memory", "quantization",
        "latency", "scale",
    ),
    "biotech_mechanics": (
        "cell", "receptor", "car-t", "crispr", "mutation", "antigen", "kinase",
        "tumor",
    ),
    "human_performance": (
        "muscle", "biomechanics", "velocity", "lactate", "joint", "hypertrophy",
        "recovery", "periodization",
    ),
    "capital_allocation": (
        "valuation", "cash flow", "dcf", "margin of safety", "moat", "capital",
        "fpa", "runway",
    ),
    "strategic_positioning": (
        "disruption", "competitive", "flywheel", "customer", "positioning",
        "market", "talent",
    ),
}


def load_genomes(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    with open(path or DATA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


class DeterministicReasoningEngine:
    """Believability-weighted multi-genome deliberation over one problem."""

    def __init__(self, genomes: Optional[Dict[str, Dict[str, Any]]] = None):
        self.genomes = genomes if genomes is not None else load_genomes()
        self.state_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ FSM

    def reason_about_problem(
        self,
        problem: str,
        selected_genomes: List[str],
        active_sectors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        active_sectors = list(active_sectors or ["dev"])
        now = self._now()
        result: Dict[str, Any] = {
            "id": f"reasoning_{int(time.time() * 1000)}",
            "problem": problem,
            "selected_genomes": selected_genomes,
            "active_sectors": active_sectors,
            "timestamp": now,
            "states": [],
            "rules": [],
            "output": None,
            "audit_trail": {},
        }

        # State 1: PERCEIVE
        detected_sector = self.detect_sector(problem, active_sectors)
        domain = self.extract_domain(problem)
        constraints = self.identify_constraints(problem)
        complexity = self.assess_complexity(problem)
        result["states"].append({
            "name": "ANALYZE_PROBLEM",
            "phase": "PERCEIVE",
            "inputs": {"problem": problem, "activeSectors": active_sectors},
            "rules": [
                "detect_sector_alignment",
                "extract_domain_heuristics",
                "identify_boundary_constraints",
                "determine_complexity",
            ],
            "outputs": {
                "sector": detected_sector,
                "domain": domain,
                "constraints": constraints,
                "complexity": complexity,
            },
        })

        # State 2: ROUTE
        ranked = self.rank_genomes_by_relevance(problem, selected_genomes)
        recommendations = self.generate_recommendations(problem, selected_genomes)
        result["states"].append({
            "name": "MATCH_GENOMES",
            "phase": "ROUTE",
            "inputs": {
                "problem": problem,
                "availableGenomes": selected_genomes,
                "activeSectors": active_sectors,
            },
            "rules": [
                "compute_believability_weighted_relevance",
                "rank_by_domain_expertise",
                "check_cross_sector_compatibility",
            ],
            "outputs": {"rankedGenomes": ranked, "recommendations": recommendations},
        })

        # State 3: SYNTHESIZE
        solution = self.synthesize_solution(ranked, problem)
        confidence = self.calculate_confidence(ranked)
        result["states"].append({
            "name": "SYNTHESIZE_SOLUTION",
            "phase": "SYNTHESIZE",
            "inputs": {"rankedGenomes": ranked, "constraints": constraints},
            "rules": [
                "apply_mental_models",
                "compose_toolchains",
                "merge_patterns",
                "resolve_competing_tradeoffs",
            ],
            "outputs": {"solution": solution, "confidence": confidence},
        })

        result["output"] = solution
        result["audit_trail"] = self.generate_audit_trail(result)
        self.state_history.append(result)
        return result

    # ------------------------------------------------------------- PERCEIVE

    @staticmethod
    def detect_sector(problem: str, active_sectors: List[str]) -> str:
        if len(active_sectors) > 1:
            return "cross_domain"
        if len(active_sectors) == 1:
            return active_sectors[0]
        p = problem.lower()
        for sector, keywords in _SECTOR_KEYWORDS.items():
            if any(kw in p for kw in keywords):
                return sector
        return "dev"

    @staticmethod
    def extract_domain(problem: str) -> str:
        p = problem.lower()
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in p for kw in keywords):
                return domain
        return "general_inquiry"

    @staticmethod
    def identify_constraints(problem: str) -> List[str]:
        lower = problem.lower()
        checks = [
            (("memory", "vram", "ram"), "memory_constrained"),
            (("fast", "latency", "real-time", "velocity"), "latency_critical"),
            (("accuracy", "precision", "safety", "toxicity"),
             "safety_and_precision_critical"),
            (("scale", "cluster", "enterprise", "multi-region"), "distributed_scale"),
            (("privacy", "security", "hipaa", "compliance"),
             "regulatory_and_privacy_enforced"),
            (("budget", "capital", "burn", "cost"), "capital_and_budget_constrained"),
            (("injury", "fatigue", "recovery"), "biological_recovery_constrained"),
        ]
        found = [label for needles, label in checks if any(n in lower for n in needles)]
        return found or ["standard_operating_envelope"]

    @staticmethod
    def assess_complexity(problem: str) -> float:
        return round(min(1.0, max(0.2, len(problem) / 300)), 6)

    # ---------------------------------------------------------------- ROUTE

    def rank_genomes_by_relevance(
        self, problem: str, genome_keys: List[str]
    ) -> List[Dict[str, Any]]:
        p_lower = problem.lower()
        ranked: List[Dict[str, Any]] = []
        for key in genome_keys:
            genome = self.genomes.get(key)
            if not genome:
                ranked.append({
                    "id": key, "name": key, "key": key, "sector": "dev",
                    "subBrain": "General", "role": "Domain Specialist",
                    "relevanceScore": 0.5, "determinismRating": 0.9,
                    "believabilityWeight": 0.9, "confidence": 0.9,
                })
                continue

            match_count = sum(
                1
                for m in genome["mentalModels"]
                if m.lower() in p_lower
                or m.lower().replace("-", " ") in p_lower
                or any(t.lower() in p_lower for t in genome["toolchain"])
                or genome["coreStrength"].lower() in p_lower
                or genome["subBrain"].lower() in p_lower
                or any(q.lower()[:15] in p_lower for q in genome["favoriteQuestions"])
            )

            base_score = match_count / max(1, len(genome["mentalModels"]))
            believability_bonus = (genome["believabilityWeight"] - 0.90) * 0.5
            final = min(0.99, max(0.65, 0.70 + base_score * 0.22 + believability_bonus))
            ranked.append({
                "id": genome["id"],
                "name": genome["name"],
                "key": key,
                "sector": genome["sector"],
                "subBrain": genome["subBrain"],
                "role": genome["role"],
                "relevanceScore": round(final, 3),
                "determinismRating": genome["determinismRating"],
                "believabilityWeight": genome["believabilityWeight"],
                "confidence": genome.get("auditTrail", [{}])[0].get("confidence", 0.95),
            })
        ranked.sort(key=lambda g: g["relevanceScore"], reverse=True)
        return ranked

    def generate_recommendations(
        self, problem: str, genomes: List[str]
    ) -> Dict[str, Any]:
        ranked = self.rank_genomes_by_relevance(problem, genomes)
        top_key = ranked[0]["key"] if ranked else ""
        genome = self.genomes.get(top_key) or self.genomes.get("andrej-karpathy")
        if not genome:
            return {}
        return {
            "primaryApproach": {
                "leader": genome["name"],
                "sector": genome["sector"],
                "strength": genome["coreStrength"],
                "mentality": genome["mentalModels"][0] if genome["mentalModels"]
                else "first-principles",
                "debugStyle": genome["debuggingStyle"],
            },
            "toolRecommendations": genome["toolchain"],
            "pattern": genome["optimizationPattern"],
        }

    # ----------------------------------------------------------- SYNTHESIZE

    def synthesize_solution(
        self, ranked_genomes: List[Dict[str, Any]], _problem: str
    ) -> Dict[str, Any]:
        top_three = ranked_genomes[:3]
        resolved = [self.genomes.get(g["key"]) for g in top_three]
        primary, secondary, tertiary = (resolved + [None, None, None])[:3]

        unique_sectors = []
        for g in ranked_genomes[:5]:
            if g["sector"] not in unique_sectors:
                unique_sectors.append(g["sector"])
        if len(unique_sectors) > 1:
            note = (
                "Cross-Sector Multi-Brain Synergy integrating "
                + ", ".join(s.upper() for s in unique_sectors)
                + " heuristics"
            )
        else:
            note = (
                "Single-Sector Deep Council Synthesis ("
                + (unique_sectors[0].upper() if unique_sectors else "DOMAIN")
                + ")"
            )

        combined_tools: List[str] = []
        for genome in (primary, secondary):
            for tool in (genome or {}).get("toolchain", []):
                if tool not in combined_tools:
                    combined_tools.append(tool)
        combined_tools = combined_tools[:6]

        chain = " → ".join(
            f"{i + 1}. {g['name']} [{g['subBrain']}] — "
            f"{round(g['relevanceScore'] * 100)}% relevance "
            f"(Believability: {round(g['believabilityWeight'] * 100)}%)"
            for i, g in enumerate(top_three)
        )

        return {
            "approach": (
                f"Believability-weighted composite synthesis across "
                f"{len(top_three)} verified leader genomes ({note})"
            ),
            "primaryPattern": (
                f"{primary['name']} ({primary['role']}): "
                f"{primary['optimizationPattern']}"
            ) if primary else "Curriculum optimization protocol",
            "secondaryValidation": (
                f"{secondary['name']} ({secondary['role']}): "
                f"{secondary['debuggingStyle']}"
            ) if secondary else "Cross-validation benchmark",
            "tertiaryInsight": (
                f"{tertiary['name']} ({tertiary['role']}): Core principle -> "
                f"\"{tertiary['mentalModels'][0]}\""
            ) if tertiary else "Reproducibility verification",
            "crossSectorSynergy": note,
            "reasoning": chain,
            "toolRecommendations": combined_tools,
        }

    @staticmethod
    def calculate_confidence(ranked_genomes: List[Dict[str, Any]]) -> Dict[str, Any]:
        subset = ranked_genomes[:4]
        if not subset:
            return {"score": 0.95, "level": "HIGH"}
        weighted_sum = sum(g["confidence"] * g["believabilityWeight"] for g in subset)
        total_weights = sum(g["believabilityWeight"] for g in subset)
        avg = round(weighted_sum / total_weights, 3)
        level = "HIGH" if avg >= 0.95 else "MEDIUM" if avg >= 0.88 else "LOW"
        return {"score": avg, "level": level}

    # ---------------------------------------------------------------- AUDIT

    def attribute_to_public_sources(
        self, genome_keys: List[str]
    ) -> List[Dict[str, Any]]:
        out = []
        for key in genome_keys:
            genome = self.genomes.get(key)
            out.append({
                "leader": genome["name"] if genome else key,
                "sector": genome["sector"] if genome else "dev",
                "subBrain": genome["subBrain"] if genome else "General",
                "sources": (genome or {}).get(
                    "publicSources", ["Public open publications and canon"]
                ),
                "voteScope": (genome or {}).get(
                    "voteScope", "Domain decision contribution"
                ),
                "auditTrail": (genome or {}).get("auditTrail") or [{
                    "source": "public_canon", "date": "2024", "confidence": 0.95,
                }],
            })
        return out

    def generate_audit_trail(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "reasoning_id": result["id"],
            "problem_input": result["problem"],
            "selected_genomes": result["selected_genomes"],
            "active_sectors": result["active_sectors"],
            "state_transitions": [
                f"{s['phase']}: {s['name']}" for s in result["states"]
            ],
            "final_output": result["output"],
            "timestamp": result["timestamp"],
            "fully_traceable": True,
            "source_attribution": self.attribute_to_public_sources(
                result["selected_genomes"]
            ),
        }

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

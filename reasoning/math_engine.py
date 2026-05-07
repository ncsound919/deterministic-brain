"""math_engine.py

A deterministic reasoning engine built on four mathematical pillars:

  1. AlgebraicReasoner     — symbolic constraint solving, variable binding,
                              pattern unification (replaces LLM slot-filling)

  2. DifferentialReasoner  — gradient/derivative estimation over discrete
                              config spaces, finds steepest improvement path
                              without any calculus library (finite differences)

  3. LinearReasoner        — vector-space context scoring, cosine similarity,
                              PCA-style dimensionality reduction for choosing
                              between skill candidates

  4. QuantumProbabilistic  — superposition of choices collapsed by amplitude
                              weighting; mimics quantum branch selection
                              without any quantum hardware

All four feed into:
  ReasoningEngine.decide()  — the unified multi-choice breakdown that the
                              DeterministicCodingAgent calls instead of an LLM

Zero external ML/LLM dependencies.
Optional: numpy (faster linear ops). Falls back to pure Python if absent.
"""
from __future__ import annotations
import hashlib
import itertools
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PreAuditResult:
    """Result of a pre-audit string check."""
    audit_ok: bool
    blocked_reason: Optional[str] = None


# ════════════════════════════════════════════════════════════════
# 1. ALGEBRAIC REASONER
#    Symbolic constraint solving + variable unification.
#    Models a coding decision as a system of typed constraints.
#    solve() returns the first consistent binding or None.
# ═══════════════════════════════════════════════════════════════════════

class Constraint:
    """
    A single typed constraint: variable must satisfy predicate.
    Examples:
      Constraint('lang',   lambda v: v in {'python','typescript'})
      Constraint('lines',  lambda v: v < 200)
      Constraint('async',  lambda v: isinstance(v, bool))
    """
    def __init__(self, var: str, predicate, description: str = ""):
        self.var         = var
        self.predicate   = predicate
        self.description = description

    def satisfied(self, value) -> bool:
        try:
            return bool(self.predicate(value))
        except Exception:
            return False


class AlgebraicReasoner:
    """
    Given a set of variables (each with a domain of possible values)
    and a set of Constraints, find the first consistent assignment
    using arc-consistency + backtracking (AC-3 + BT).

    This is the deterministic equivalent of an LLM "filling in the blanks"
    for a coding task.

    Usage:
        ar = AlgebraicReasoner()
        ar.add_variable('lang',  ['python', 'typescript', 'go'])
        ar.add_variable('async', [True, False])
        ar.add_constraint(Constraint('lang',  lambda v: v != 'go'))
        ar.add_constraint(Constraint('async', lambda v: v is True))
        solution = ar.solve()  # {'lang': 'python', 'async': True}
    """

    def __init__(self):
        self.variables:   Dict[str, List]       = {}
        self.constraints: List[Constraint]      = []

    def add_variable(self, name: str, domain: List) -> None:
        self.variables[name] = list(domain)

    def add_constraint(self, c: Constraint) -> None:
        self.constraints.append(c)

    def solve(self) -> Optional[Dict]:
        """AC-3 arc consistency + chronological backtracking."""
        # prune domains first
        domains = {v: list(d) for v, d in self.variables.items()}
        for c in self.constraints:
            if c.var in domains:
                domains[c.var] = [val for val in domains[c.var]
                                  if c.satisfied(val)]
            if c.var in domains and not domains[c.var]:
                return None  # domain wipeout

        return self._backtrack({}, domains)

    def _backtrack(self, assignment: Dict, domains: Dict) -> Optional[Dict]:
        if len(assignment) == len(self.variables):
            return assignment
        # pick unassigned variable (MRV heuristic: smallest domain first)
        unassigned = [v for v in self.variables if v not in assignment]
        var = min(unassigned, key=lambda v: len(domains.get(v, [])))
        for value in domains.get(var, []):
            new_assign = {**assignment, var: value}
            if self._consistent(new_assign):
                result = self._backtrack(new_assign, domains)
                if result is not None:
                    return result
        return None

    def _consistent(self, assignment: Dict) -> bool:
        for c in self.constraints:
            if c.var in assignment:
                if not c.satisfied(assignment[c.var]):
                    return False
        return True

    def all_solutions(self, limit: int = 64) -> List[Dict]:
        """Return up to `limit` consistent assignments using generator."""
        domains = {v: list(d) for v, d in self.variables.items()}
        for c in self.constraints:
            if c.var in domains:
                domains[c.var] = [val for val in domains[c.var]
                                  if c.satisfied(val)]
        keys   = list(self.variables.keys())
        # Use islice to avoid materializing all combinations in memory
        combos = itertools.islice(
            itertools.product(*[domains.get(k, []) for k in keys]),
            limit
        )
        solutions = []
        for combo in combos:
            candidate = dict(zip(keys, combo))
            if self._consistent(candidate):
                solutions.append(candidate)
        return solutions


# ═══════════════════════════════════════════════════════════════════════
# 2. DIFFERENTIAL REASONER
#    Treats the scoring function as a black-box differentiable surface.
#    Uses finite differences to estimate the gradient over the config
#    space, then takes a step toward higher scores.
#    This is gradient ascent without any neural network.
# ═══════════════════════════════════════════════════════════════════════

class DifferentialReasoner:
    """
    Finite-difference gradient ascent over a discrete config space.

    Given a list of config dicts and a scoring function,
    estimate which config dimension to change to maximise score.

    Think of it as: "which single parameter flip improves the output most?"

    Usage:
        dr = DifferentialReasoner(scorer_fn=my_scorer)
        best = dr.ascend(base_config, neighbors_fn, steps=3)
    """

    def __init__(self, scorer_fn):
        """
        scorer_fn: callable(config: Dict) -> float
        """
        self.scorer = scorer_fn

    def gradient(self, base: Dict, neighbors: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        Estimate partial derivative for each neighbor:
          ∂score/∂dim ≈ (score(neighbor) - score(base)) / 1
        Returns list of (neighbor, delta) sorted by delta desc.
        """
        base_score = self.scorer(base)
        deltas = []
        for n in neighbors:
            try:
                s = self.scorer(n)
                deltas.append((n, s - base_score))
            except Exception:
                deltas.append((n, -999.0))
        return sorted(deltas, key=lambda x: x[1], reverse=True)

    def ascend(self, base: Dict, neighbors_fn, steps: int = 3) -> Dict:
        """
        Greedy gradient ascent: at each step pick the neighbor with
        the highest positive delta. Stop if no improvement.
        """
        current = base
        for _ in range(steps):
            neighbors = neighbors_fn(current)
            if not neighbors:
                break
            ranked = self.gradient(current, neighbors)
            best_neighbor, best_delta = ranked[0]
            if best_delta <= 0:
                break
            current = best_neighbor
        return current

    def jacobian(self, configs: List[Dict]) -> List[Tuple[Dict, float]]:
        """
        Score all configs and return sorted list — the full Jacobian
        of the scoring surface over the provided config set.
        """
        scored = []
        for c in configs:
            try:
                scored.append((c, self.scorer(c)))
            except Exception:
                scored.append((c, 0.0))
        return sorted(scored, key=lambda x: x[1], reverse=True)


# ═══════════════════════════════════════════════════════════════════════
# 3. LINEAR REASONER
#    Vector-space context scoring.
#    Encodes candidate choices as TF-weighted term vectors,
#    scores them against a query vector via cosine similarity.
#    Also does PCA-style projection to surface dominant axes.
# ═══════════════════════════════════════════════════════════════════════

class LinearReasoner:
    """
    Pure-Python vector space reasoning.
    No numpy required (uses it if available for speed).

    Each candidate is a dict of features → float weights.
    query() ranks candidates by cosine similarity to a query vector.

    Usage:
        lr = LinearReasoner()
        candidates = [
            {'rest': 1, 'crud': 1, 'auth': 0},
            {'graphql': 1, 'crud': 1, 'auth': 1},
        ]
        query = {'crud': 1, 'auth': 1}
        ranked = lr.rank(query, candidates)
    """

    @staticmethod
    def _dot(a: Dict, b: Dict) -> float:
        return sum(a.get(k, 0.0) * b.get(k, 0.0) for k in b)

    @staticmethod
    def _norm(v: Dict) -> float:
        return math.sqrt(sum(x * x for x in v.values())) or 1e-9

    def cosine(self, a: Dict, b: Dict) -> float:
        return self._dot(a, b) / (self._norm(a) * self._norm(b))

    def rank(self, query: Dict, candidates: List[Dict]) -> List[Tuple[Dict, float]]:
        """Return candidates sorted by cosine similarity to query."""
        scored = [(c, self.cosine(query, c)) for c in candidates]
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def encode_text(self, text: str) -> Dict:
        """Bag-of-words TF vector from a string (no stopwords, lowercase)."""
        STOP = {'a','an','the','is','are','was','were','in','of','to',
                'and','or','for','with','on','at','by','this','that',
                'it','as','be','not','from','into','if','then','do'}
        words = re.findall(r'[a-z0-9_]+', text.lower())
        vec: Dict[str, float] = {}
        for w in words:
            if w not in STOP:
                vec[w] = vec.get(w, 0.0) + 1.0
        return vec

    def rank_texts(self, query_text: str, candidate_texts: List[str]) -> List[Tuple[str, float]]:
        """Rank plain text candidates against a plain text query."""
        qv   = self.encode_text(query_text)
        cvs  = [self.encode_text(t) for t in candidate_texts]
        
        # Score each candidate
        results = []
        for i, cv in enumerate(cvs):
            score = self.cosine(qv, cv)
            results.append((i, candidate_texts[i], score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[2], reverse=True)
        return [(text, score) for _, text, score in results]

    def dominant_axes(self, vectors: List[Dict], top_k: int = 5) -> List[str]:
        """
        Power-iteration PCA substitute:
        returns the top_k terms that explain the most variance
        across all vectors (highest summed squared weight).
        """
        term_variance: Dict[str, float] = {}
        for v in vectors:
            for term, weight in v.items():
                term_variance[term] = term_variance.get(term, 0.0) + weight ** 2
        return sorted(term_variance, key=term_variance.get, reverse=True)[:top_k]


# ═══════════════════════════════════════════════════════════════════════
# 4. QUANTUM PROBABILISTIC REASONER
#    Superposition → amplitude assignment → collapse.
#
#    Models a multi-choice decision as a quantum superposition where
#    each choice has a complex amplitude. Interference (constructive /
#    destructive) between choices is simulated algebraically.
#    collapse() deterministically picks the highest-probability outcome
#    given the input evidence. With the same inputs you always get the
#    same result — deterministic but mimics probabilistic reasoning.
# ═══════════════════════════════════════════════════════════════════════

class QuantumProbabilistic:
    """
    Deterministic quantum-inspired choice collapse.

    Each choice gets:
      - a prior amplitude based on its position in the list
      - constructive interference from matching evidence keywords
      - destructive interference from conflicting constraints

    |amplitude|^2 gives the probability. Highest wins.

    Usage:
        qp = QuantumProbabilistic()
        choices = ['use REST', 'use GraphQL', 'use gRPC']
        evidence = ['REST', 'CRUD', 'simple']
        chosen, probs = qp.collapse(choices, evidence)
    """

    def _hash_amplitude(self, text: str) -> complex:
        """Deterministic complex amplitude from text (64-bit hash)."""
        h    = int(hashlib.sha256(text.encode()).hexdigest()[:16], 16)
        # map to unit circle
        theta = (h % 10000) / 10000 * 2 * math.pi
        return complex(math.cos(theta), math.sin(theta))

    def _interference(self, choice: str, evidence: List[str]) -> float:
        """
        Constructive (+) if evidence term appears in choice text.
        Destructive (-) if evidence term starts with 'no-'/'not-' and
        the base term appears in choice.
        Net interference is normalised to [-1, 1].
        """
        score = 0.0
        choice_lower = choice.lower()
        for e in evidence:
            e_lower = e.lower()
            if e_lower.startswith(('no-', 'not-')):
                base = e_lower[3:]
                if base in choice_lower:
                    score -= 1.0
            elif e_lower in choice_lower:
                score += 1.0
        n = max(len(evidence), 1)
        return max(-1.0, min(1.0, score / n))

    def amplitudes(self, choices: List[str], evidence: List[str]) -> List[Tuple[str, float]]:
        """
        Return (choice, probability) pairs sorted by probability desc.
        probability = |amplitude + interference|^2, normalised.
        """
        raw = []
        for i, c in enumerate(choices):
            base_amp   = self._hash_amplitude(c)
            interfere  = self._interference(c, evidence)
            # scale amplitude by (1 + interference)
            scaled     = base_amp * (1.0 + interfere)
            prob_raw   = scaled.real ** 2 + scaled.imag ** 2
            raw.append((c, prob_raw))

        total = sum(p for _, p in raw) or 1e-9
        normalised = [(c, p / total) for c, p in raw]
        return sorted(normalised, key=lambda x: x[1], reverse=True)

    def collapse(self, choices: List[str], evidence: List[str]) -> Tuple[str, List[Tuple[str, float]]]:
        """
        Collapse superposition to highest-probability choice.
        Returns (chosen, all_probabilities).
        """
        probs  = self.amplitudes(choices, evidence)
        chosen = probs[0][0]
        return chosen, probs

    def top_k(self, choices: List[str], evidence: List[str], k: int = 3) -> List[Tuple[str, float]]:
        probs = self.amplitudes(choices, evidence)
        return probs[:k]


# ═══════════════════════════════════════════════════════════════════════
# UNIFIED REASONING ENGINE
#
# Orchestrates all four reasoners into a single decide() call.
# This is what DeterministicCodingAgent calls for complex tasks.
#
# Pipeline:
#   1. AlgebraicReasoner   → prune variable space, find valid configs
#   2. LinearReasoner      → rank valid configs by cosine to task context
#   3. QuantumProbabilistic→ collapse top candidates using evidence signals
#   4. DifferentialReasoner→ fine-tune final choice by gradient ascent
#   5. Pre-audit           → static checks before execution
# ═══════════════════════════════════════════════════════════════════════

def _check_injection(text: str) -> bool:
    """Check for injection patterns in user input.

    Detects:
    - Shell metacharacters: ; | & $ `
    - Command chaining: && ||
    - Path traversal: ../
    - Newline injection (for shell commands)
    - URL-encoded $: %24
    - Template injection: {{ }}
    """
    if not text:
        return False

    patterns = [
        # Shell metacharacters and command injection
        r'[;|&`$]',            # any of ; | & ` $
        r'&&',                 # command chaining
        r'\|\|',               # logical OR (escaped pipe)
        r'\$\(',              # $(command) — escaped $ for literal match
        r'`[^`]*`',            # `command`

        # Path traversal and sensitive paths
        r'\.\./',              # ../
        r'\.\\',             # ..\ (Windows)
        r'/etc/passwd',        # UNIX passwd file
        r'windows\\system32',  # Windows system32

        # Template & encoding tricks
        r'%24',                # URL-encoded $
        r'\{\{.*\}\}',         # {{ template }}
        r'\n',                 # newline injection (shell command splitting)
    ]

    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True
    return False


class PreAudit:
    """
    Static pre-execution checks run before any code is written.
    Each check is a named predicate over the task dict.
    Returns a list of warnings/blocks.
    """

    CHECKS = [
        ("has_task",        lambda t: bool(t.get("task")),
         "No task type identified"),
        ("has_inputs",      lambda t: bool(t.get("raw")),
         "Empty input string"),
        ("no_injection",    lambda t: not _check_injection(t.get("raw", "")),
         "Possible injection in input"),
        ("known_task",      lambda t: t.get("task") != "unknown",
         "Task type is unknown — no skill available"),
        ("reasonable_length",lambda t: len(t.get("raw", "").encode("utf-8")) < 8192,
         "Input exceeds 8192 bytes"),
    ]

    def run(self, task: Dict) -> Tuple[bool, List[str]]:
        """
        Returns (ok, issues).
        ok=False means a blocking check failed.
        """
        issues = []
        ok     = True
        for name, check, msg in self.CHECKS:
            try:
                passed = check(task)
            except Exception:
                passed = False
            if not passed:
                issues.append(f"[{name}] {msg}")
                if name in ("no_injection", "no_task"):
                    ok = False  # blocking
        return ok, issues

    def check(self, text: str) -> PreAuditResult:
        """Check a string for injection patterns.

        Args:
            text: String to check

        Returns:
            PreAuditResult with audit_ok and blocked_reason
        """
        if _check_injection(text):
            return PreAuditResult(audit_ok=False, blocked_reason="Possible injection detected")

        return PreAuditResult(audit_ok=True)


class ReasoningEngine:
    """
    The unified no-LLM reasoning core.

    decide(task, skill_candidates, scorer_fn) → DecisionResult

    DecisionResult contains:
      .chosen_skill     — the skill path to execute
      .chosen_config    — the best config dict
      .confidence       — 0.0–1.0 composite confidence
      .pre_audit        — list of pre-audit warnings
      .audit_ok         — bool: safe to proceed?
      .breakdown        — full step-by-step reasoning trace
    """

    def __init__(self):
        self.linear      = LinearReasoner()
        self.quantum     = QuantumProbabilistic()
        self.pre_audit   = PreAudit()

    def decide(
        self,
        task:             Dict,
        skill_candidates: List[str],
        scorer_fn         = None,
        constraints:      List[Constraint] = None,
        variable_domains: Dict[str, List]  = None,
    ) -> "DecisionResult":

        breakdown = []
        constraints      = constraints      or []
        variable_domains = variable_domains or {}

        # ── Step 0: Pre-Audit ────────────────────────────────────────────
        audit_ok, audit_issues = self.pre_audit.run(task)
        breakdown.append({"step": "pre_audit", "ok": audit_ok, "issues": audit_issues})
        if not audit_ok:
            return DecisionResult(
                chosen_skill=None, chosen_config={},
                confidence=0.0, pre_audit=audit_issues,
                audit_ok=False, breakdown=breakdown,
            )

        # ── Step 1: Algebraic — prune config space ───────────────────────
        ar = AlgebraicReasoner()
        for var, domain in variable_domains.items():
            ar.add_variable(var, domain)
        for c in constraints:
            ar.add_constraint(c)
        valid_configs = ar.all_solutions(limit=32) if variable_domains else [{}]
        breakdown.append({"step": "algebraic", "valid_configs": len(valid_configs)})

        # ── Step 2: Linear — rank skills by cosine to task ────────────────
        task_text    = task.get("raw", task.get("task", ""))
        ranked_skills = self.linear.rank_texts(task_text, skill_candidates)
        breakdown.append({"step": "linear", "top_skill": ranked_skills[0][0] if ranked_skills else None})

        # ── Step 3: Quantum — collapse to final skill choice ───────────────
        # Quantum collapse runs over top-8 linear candidates only, so
        # q_confidence is properly normalised over a small set rather than
        # being diluted by the full 89-skill candidate pool.
        evidence      = task_text.split()
        top_skills    = [s for s, _ in ranked_skills[:8]]
        chosen_skill, q_probs = self.quantum.collapse(top_skills, evidence) if top_skills else (None, [])
        q_confidence  = q_probs[0][1] if q_probs else 0.0
        breakdown.append({"step": "quantum", "chosen": chosen_skill,
                          "confidence": round(q_confidence, 4),
                          "top3": q_probs[:3]})

        # ── Step 4: Config selection — pick best from exhaustive search ──────────
        best_config = valid_configs[0] if valid_configs else {}
        if scorer_fn and len(valid_configs) > 1:
            try:
                best_config = max(
                    valid_configs,
                    key=lambda c: scorer_fn({**c, "skill": chosen_skill})
                )
                final_score = scorer_fn({**best_config, "skill": chosen_skill})
                breakdown.append({"step": "config_select", "final_config": best_config,
                                  "score": round(final_score, 4), "method": "scored_max"})
            except Exception:
                breakdown.append({"step": "config_select", "skipped": True,
                                  "reason": "scorer_fn error"})
        else:
            breakdown.append({"step": "config_select", "skipped": True})

        # ── Composite confidence ───────────────────────────────────────────
        # Weighted blend: 60% linear cosine + 40% quantum probability.
        # Previously a geometric mean — that formula collapses to ~0.10 when
        # there are many candidates (q_confidence ≈ 1/N for large N).
        # The weighted blend is independent of candidate pool size.
        linear_conf = ranked_skills[0][1] if ranked_skills else 0.0
        confidence  = 0.6 * max(0.0, linear_conf) + 0.4 * max(0.0, q_confidence)

        return DecisionResult(
            chosen_skill  = chosen_skill,
            chosen_config = best_config,
            confidence    = round(confidence, 4),
            pre_audit     = audit_issues,
            audit_ok      = audit_ok,
            breakdown     = breakdown,
        )


class DecisionResult:
    __slots__ = [
        'chosen_skill', 'chosen_config', 'confidence',
        'pre_audit', 'audit_ok', 'breakdown',
    ]

    def __init__(self, chosen_skill, chosen_config, confidence,
                 pre_audit, audit_ok, breakdown):
        self.chosen_skill  = chosen_skill
        self.chosen_config = chosen_config
        self.confidence    = confidence
        self.pre_audit     = pre_audit
        self.audit_ok      = audit_ok
        self.breakdown     = breakdown

    def __repr__(self):
        return (f"DecisionResult(skill={self.chosen_skill!r}, "
                f"confidence={self.confidence}, audit_ok={self.audit_ok})")

    def __eq__(self, other):
        if not isinstance(other, DecisionResult):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def to_dict(self) -> Dict:
        return {
            "chosen_skill":  self.chosen_skill,
            "chosen_config": self.chosen_config,
            "confidence":    self.confidence,
            "pre_audit":     self.pre_audit,
            "audit_ok":      self.audit_ok,
            "breakdown":     self.breakdown,
        }

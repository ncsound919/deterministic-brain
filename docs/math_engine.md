# Math Engine — Deterministic Reasoning Without LLMs

The `reasoning/math_engine.py` replaces probabilistic LLM inference with
four mathematically grounded subsystems. Each maps a classical field of
mathematics to a specific reasoning problem in coding agent decisions.

---

## 1. Algebraic Reasoner — Constraint Satisfaction

**Mathematical basis:** Boolean algebra, constraint satisfaction (CSP), arc-consistency (AC-3)

**What it solves:** "Given the task requires TypeScript + async + under 200 lines, which configs are valid?"

- Each task parameter is a **variable** with a **domain** of allowed values
- Each rule is a **Constraint** (a typed predicate)
- AC-3 prunes inconsistent values from all domains before backtracking
- Backtracking uses the **MRV heuristic** (most constrained variable first)
- Returns all consistent assignments up to a limit of 32

**Why it works:** A coding decision *is* a CSP. Language, framework, async/sync, line budget, auth method — all are variables with discrete domains and inter-variable constraints.

---

## 2. Differential Reasoner — Gradient Ascent

**Mathematical basis:** Differential calculus, finite differences, gradient ascent

**What it solves:** "Which single config change improves the audit score the most?"

```
∂score/∂dim ≈ (score(config + Δdim) - score(config)) / 1
```

- Treats the `DeterministicScorer` as a black-box function `f: Config → float`
- Estimates partial derivatives via **finite differences** (no symbolic math needed)
- **Greedy gradient ascent**: at each step, pick the neighbor with the highest positive delta
- Stops when no neighbor improves the score (local maximum)
- `jacobian()` scores the full config surface at once

**Why it works:** The scoring surface (complexity + coverage + line count) is smooth enough that greedy ascent reliably finds good configurations in 2–3 steps.

---

## 3. Linear Reasoner — Vector Space Context

**Mathematical basis:** Linear algebra, TF-weighted bag-of-words, cosine similarity, variance decomposition

**What it solves:** "Which skill is most similar to the task description?"

```
cos(θ) = (A · B) / (‖A‖ · ‖B‖)
```

- Encodes each skill name and task description as a **TF term vector** (bag of words)
- Computes cosine similarity between query vector and each candidate vector
- `dominant_axes()` uses squared-weight variance to find the most discriminating terms (PCA substitute)
- Pure Python fallback; uses numpy if available

**Why it works:** Skill selection is a nearest-neighbor search in term space. Cosine similarity is sufficient for short structured strings like skill names and task descriptions.

---

## 4. Quantum Probabilistic — Superposition Collapse

**Mathematical basis:** Quantum mechanics (amplitude, superposition, Born rule), complex number arithmetic

**What it solves:** "Given multiple plausible skill choices, which one should we commit to?"

**How it works:**
1. Each choice gets a **base amplitude** α = e^(iθ) derived deterministically from its SHA-256 hash
2. Evidence keywords cause **constructive interference** (matching terms boost |amplitude|)
3. Negated evidence (`no-auth`, `not-rest`) causes **destructive interference** (reduce |amplitude|)
4. Probability = |amplitude|^2 (Born rule), normalised across all choices
5. **Collapse**: highest probability wins — deterministically, same input always gives same output

```
P(choice_i) = |\alpha_i (1 + interference_i)|^2 / Z
```

**Why it works:** It’s a principled way to weight multiple candidates against evidence without a lookup table or LLM. The determinism comes from the hash-derived amplitude; the sensitivity comes from the interference term.

---

## Unified Pipeline: `ReasoningEngine.decide()`

```
Task Input
    │
    ├─ [0] PreAudit       — injection check, unknown task block, length guard
    ├─ [1] AlgebraicReasoner   → valid_configs[]          (CSP solve)
    ├─ [2] LinearReasoner      → ranked_skills[]           (cosine similarity)
    ├─ [3] QuantumProbabilistic → chosen_skill, confidence  (amplitude collapse)
    └─ [4] DifferentialReasoner → best_config               (gradient ascent)
            │
            ▼
        DecisionResult
          .chosen_skill    — which skill.md to run
          .chosen_config   — best parameter set
          .confidence      — geometric mean(linear, quantum)
          .pre_audit       — warnings before execution
          .audit_ok        — safe to proceed?
          .breakdown       — full step trace
```

---

## Confidence Formula

```
confidence = sqrt(cosine_similarity * quantum_probability)
```

This is the **geometric mean** of the two independent signals:
- `cosine_similarity` measures structural match (text space)
- `quantum_probability` measures evidence alignment (amplitude space)

Geometric mean penalises asymmetry: if either signal is weak, confidence drops.
Threshold for execution: **confidence ≥ 0.30**. Below that, the engine returns
a structured error instead of running a skill.

---

## No External Dependencies

| Subsystem | Pure Python | Optional speedup |
|---|---|---|
| AlgebraicReasoner | ✓ itertools, built-ins | — |
| DifferentialReasoner | ✓ pure function calls | — |
| LinearReasoner | ✓ math.sqrt, dict ops | numpy for large corpora |
| QuantumProbabilistic | ✓ hashlib, cmath | — |
| PreAudit | ✓ re, built-ins | — |

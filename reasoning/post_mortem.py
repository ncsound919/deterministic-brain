"""Dev Brain — post-mortem calibration engine.

Ported from ncsound919/Dev-Brain src/engine/postMortemEngine.ts.
Brier-score-based decision calibration with automatic genome believability
adjustment recommendations. Feeds the deterministic-brain feedback loop:
post-mortem outcomes adjust the weights Dev Brain's council uses next time.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .dev_brain import DeterministicReasoningEngine


class PostMortemCalibrationEngine:
    def __init__(
        self,
        records: Optional[List[Dict[str, Any]]] = None,
        genomes: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.records: List[Dict[str, Any]] = list(records or [])
        self._engine = DeterministicReasoningEngine(genomes=genomes)

    # ------------------------------------------------------------- records

    def get_all_records(self) -> List[Dict[str, Any]]:
        return self.records

    def get_record_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        for r in self.records:
            if r["id"] == record_id:
                return r
        return None

    def add_record(self, record: Dict[str, Any]) -> None:
        self.records.insert(0, record)

    # ---------------------------------------------------------- calibration

    @staticmethod
    def calculate_brier_score(predicted: float, actual_binary: float) -> float:
        diff = predicted - actual_binary
        return round(diff * diff, 4)

    @staticmethod
    def get_calibration_rating(
        brier: float, predicted: float, actual: float
    ) -> str:
        if brier < 0.04:
            return "EXCELLENT"
        if brier < 0.10:
            return "GOOD"
        if predicted > 0.75 and actual == 0:
            return "OVERCONFIDENT"
        if predicted < 0.40 and actual == 1:
            return "UNDERCONFIDENT"
        return "MISCALIBRATED"

    def compute_overview(self) -> Dict[str, Any]:
        completed = [r for r in self.records if r.get("status") != "pending"]
        if not completed:
            return {
                "totalDecisionsLogged": 0,
                "meanBrierScore": 0,
                "calibrationGrade": "A",
                "overconfidenceBiasScore": 0,
                "accuracyRate": 0,
                "sectorPerformance": [],
            }

        mean_brier = sum(r["brierScore"] for r in completed) / len(completed)

        if mean_brier > 0.20:
            grade = "D"
        elif mean_brier > 0.12:
            grade = "C"
        elif mean_brier > 0.06:
            grade = "B"
        elif mean_brier > 0.03:
            grade = "A"
        else:
            grade = "A+"

        success_count = len([r for r in completed if r["actualOutcomeBinary"] >= 0.8])
        accuracy_rate = round(success_count / len(completed) * 100, 1)

        sector_performance = []
        for sector in ("dev", "business", "financial", "science_biotech",
                       "science_sports"):
            sec_records = [r for r in completed if r["sector"] == sector]
            if not sec_records:
                sector_performance.append({
                    "sector": sector, "decisionsCount": 0,
                    "avgBrier": 0, "successRate": 100,
                })
                continue
            sec_brier = sum(r["brierScore"] for r in sec_records) / len(sec_records)
            sec_success = len(
                [r for r in sec_records if r["actualOutcomeBinary"] >= 0.8]
            )
            sector_performance.append({
                "sector": sector,
                "decisionsCount": len(sec_records),
                "avgBrier": round(sec_brier, 4),
                "successRate": round(sec_success / len(sec_records) * 100, 1),
            })

        return {
            "totalDecisionsLogged": len(self.records),
            "meanBrierScore": round(mean_brier, 4),
            "calibrationGrade": grade,
            "overconfidenceBiasScore": 2.4,
            "accuracyRate": accuracy_rate,
            "sectorPerformance": sector_performance,
        }

    # ------------------------------------------------------------- creation

    def create_new_post_mortem(
        self,
        decision_title: str,
        sector: str,
        chosen_option: str,
        predicted_probability: float,
        actual_outcome: str,
        metric_variances: List[Dict[str, Any]],
        root_causes: List[str],
        key_lessons: List[str],
        retrospective_summary: str,
        leaders: List[Dict[str, Any]],
        decision_date: Optional[str] = None,
        evaluation_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        actual_binary = (
            1.0 if actual_outcome == "success"
            else 0.5 if actual_outcome == "partial" else 0.0
        )
        brier = self.calculate_brier_score(predicted_probability, actual_binary)
        rating = self.get_calibration_rating(
            brier, predicted_probability, actual_binary
        )

        suggested: List[Dict[str, Any]] = []
        relevant = next((l for l in leaders if l["sector"] == sector), None)
        if relevant:
            delta = (
                +0.01 if actual_outcome == "success"
                else -0.02 if actual_outcome == "failure" else 0.0
            )
            recommended = min(1.0, max(0.5, round(relevant["believabilityWeight"] + delta, 2)))
            suggested.append({
                "leaderId": relevant["id"],
                "leaderName": relevant["name"],
                "sector": relevant["sector"],
                "currentBelievability": relevant["believabilityWeight"],
                "recommendedBelievability": recommended,
                "delta": delta,
                "reason": (
                    f"Outcome calibration: {actual_outcome.upper()} "
                    f"(Brier: {brier}) on \"{decision_title}\"."
                ),
            })

        now = time.time()
        record: Dict[str, Any] = {
            "id": f"pm-{format(int(now * 1000), 'x')}",
            "decisionTitle": decision_title,
            "sector": sector,
            "decisionDate": decision_date
            or time.strftime("%Y-%m-%d", time.gmtime(now - 30 * 86400)),
            "evaluationDate": evaluation_date
            or time.strftime("%Y-%m-%d", time.gmtime(now)),
            "status": actual_outcome,
            "chosenOption": chosen_option,
            "predictedProbability": predicted_probability,
            "actualOutcomeBinary": actual_binary,
            "brierScore": brier,
            "calibrationRating": rating,
            "metricVariances": metric_variances,
            "rootCauses": root_causes,
            "keyLessons": key_lessons,
            "suggestedAdjustments": suggested,
            "retrospectiveSummary": retrospective_summary,
        }
        self.add_record(record)
        return record

    def apply_adjustments(self, record_id: str) -> int:
        """Apply a post-mortem's suggested believability adjustments to the
        genome data this engine was constructed with. Returns count applied."""
        record = self.get_record_by_id(record_id)
        if not record:
            return 0
        applied = 0
        for adj in record.get("suggestedAdjustments", []):
            genome = self._engine.genomes.get(adj["leaderId"])
            if genome and genome["believabilityWeight"] != adj["recommendedBelievability"]:
                genome["believabilityWeight"] = adj["recommendedBelievability"]
                applied += 1
        return applied

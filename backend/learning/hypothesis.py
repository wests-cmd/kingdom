import time
import secrets
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class IntelligenceHypothesis(BaseModel):
    id: str = Field(default_factory=lambda: f"hyp_{secrets.token_hex(6)}")
    subsystem: str
    observation: str
    proposed_optimization: str
    expected_latency_delta_pct: float = -15.0
    expected_accuracy_delta_pct: float = 0.0
    status: str = "PROPOSED" # PROPOSED, TESTING, VALIDATED, REJECTED
    created_at: float = Field(default_factory=time.time)

class HypothesisEngine:
    def __init__(self):
        self.hypotheses: Dict[str, IntelligenceHypothesis] = {}

    def generate_hypothesis(self, subsystem: str, observation: str, proposed_optimization: str) -> IntelligenceHypothesis:
        hyp = IntelligenceHypothesis(
            subsystem=subsystem,
            observation=observation,
            proposed_optimization=proposed_optimization
        )
        self.hypotheses[hyp.id] = hyp
        return hyp

    def evaluate_hypothesis_in_sandbox(self, hypothesis_id: str, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        hyp = self.hypotheses.get(hypothesis_id)
        if not hyp:
            return {"success": False, "error": f"Hypothesis {hypothesis_id} not found."}

        # Multi-Metric Gating: Latency improvement without accuracy or security degradation
        latency_improved = benchmark_results.get("latency_delta_pct", 0) <= -5.0
        accuracy_maintained = benchmark_results.get("accuracy_delta_pct", 0) >= 0.0
        no_security_violations = benchmark_results.get("security_violations", 0) == 0

        if latency_improved and accuracy_maintained and no_security_violations:
            hyp.status = "VALIDATED"
            return {
                "success": True,
                "hypothesis_id": hypothesis_id,
                "status": "VALIDATED",
                "message": "Hypothesis validated in sandbox benchmarks. Eligible for governance promotion."
            }
        else:
            hyp.status = "REJECTED"
            return {
                "success": False,
                "hypothesis_id": hypothesis_id,
                "status": "REJECTED",
                "reason": "Sandbox multi-metric evaluation failed (accuracy drop, security violation, or insufficient speedup)."
            }

hypothesis_engine = HypothesisEngine()

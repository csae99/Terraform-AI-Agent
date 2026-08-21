from typing import Dict, List, Any

class ConsensusScorer:
    """
    Multi-Dimensional Consensus Scoring Matrix.
    Evaluates competing IaC architectural proposals across:
    - Security & Compliance (35%)
    - Cost Efficiency (25%)
    - Reliability & Resilience (25%)
    - Simplicity & Maintainability (15%)
    """

    WEIGHTS = {
        "security": 0.35,
        "cost": 0.25,
        "reliability": 0.25,
        "simplicity": 0.15
    }

    @classmethod
    def score_proposal(
        cls,
        name: str,
        security_score: float,   # 0 - 100
        cost_score: float,       # 0 - 100 (100 = most cost-effective)
        reliability_score: float,# 0 - 100
        simplicity_score: float, # 0 - 100
        hcl_snippet: str = "",
        rationale: str = ""
    ) -> Dict[str, Any]:
        """Calculates weighted composite consensus score for an architecture proposal."""
        composite = (
            security_score * cls.WEIGHTS["security"] +
            cost_score * cls.WEIGHTS["cost"] +
            reliability_score * cls.WEIGHTS["reliability"] +
            simplicity_score * cls.WEIGHTS["simplicity"]
        )

        return {
            "proposal_name": name,
            "composite_score": round(composite, 2),
            "breakdown": {
                "security": security_score,
                "cost": cost_score,
                "reliability": reliability_score,
                "simplicity": simplicity_score
            },
            "weights": cls.WEIGHTS,
            "hcl_snippet": hcl_snippet,
            "rationale": rationale
        }

    @classmethod
    def rank_proposals(cls, proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ranks multiple proposals in descending order of composite consensus score."""
        return sorted(proposals, key=lambda p: p.get("composite_score", 0), reverse=True)

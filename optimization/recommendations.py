from typing import Dict, List, Any
from optimization.finops_optimizer import FinOpsOptimizer

class RecommendationEngine:
    """
    Unified Recommendations & Actionable Insights Engine.
    Aggregates FinOps cost savings, security enhancements, and reliability recommendations.
    """

    @classmethod
    def get_workspace_recommendations(cls, hcl_code: str, current_cost: float = 100.0) -> List[Dict[str, Any]]:
        finops = FinOpsOptimizer.analyze_cost_optimizations(hcl_code)
        cards = []

        # FinOps Cards
        for rec in finops.get("recommendations", []):
            cards.append({
                "type": "COST_OPTIMIZATION",
                "badge": "FinOps",
                "title": rec["title"],
                "impact": f"+${rec['monthly_savings_usd']}/mo savings",
                "description": rec["description"],
                "auto_fixable": True
            })

        # Resilience Card
        if "multi_az" not in hcl_code.lower() and "prod" in hcl_code.lower():
            cards.append({
                "type": "RELIABILITY",
                "badge": "High Availability",
                "title": "Enable Multi-AZ Database Redundancy",
                "impact": "99.99% SLA Upgrade",
                "description": "Production database instances should configure multi_az = true for zero-downtime automated failover.",
                "auto_fixable": True
            })

        return cards

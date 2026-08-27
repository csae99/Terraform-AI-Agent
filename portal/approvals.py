from typing import Dict, Any

class ApprovalEngine:
    """
    Dynamic Risk-Weighted Approval Gate Evaluator.
    Determines whether an infrastructure change can be auto-promoted or requires manual sign-off.
    """

    @classmethod
    def evaluate_approval_rules(
        cls,
        estimated_cost: float,
        risk_score: float,
        environment: str = "staging",
        user_role: str = "Developer"
    ) -> Dict[str, Any]:
        """
        Evaluates environment, cost, and blast radius risk to determine approval requirements.
        """
        env = environment.lower()
        requires_signoff = False
        reasons = []

        # 1. Environment Policy
        if env in ["prod", "production"]:
            requires_signoff = True
            reasons.append("Production environment mutations require Owner or Admin approval.")

        # 2. Budget Threshold Policy
        if estimated_cost > 250.0:
            requires_signoff = True
            reasons.append(f"Projected spend (${estimated_cost}/mo) exceeds auto-approval threshold of $250/mo.")

        # 3. Blast Radius Risk Policy
        if risk_score > 60.0:
            requires_signoff = True
            reasons.append(f"High risk score ({risk_score}/100) indicates destructive or sensitive network alterations.")

        return {
            "auto_approved": not requires_signoff,
            "requires_human_signoff": requires_signoff,
            "required_role": "Owner" if (risk_score > 80 or env in ["prod", "production"]) else "Admin",
            "environment": environment,
            "estimated_cost": estimated_cost,
            "risk_score": risk_score,
            "reasons": reasons
        }

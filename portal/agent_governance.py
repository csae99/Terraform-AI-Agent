import re
from typing import Dict, List, Any

class AgentGovernanceFramework:
    """
    AI Agent Governance & Risk Scoring Framework.
    Enforces agent permission policies, evaluates blast radius, and computes risk scores for IaC plans.
    """

    AGENT_PERMISSIONS = {
        "ArchitectAgent": {"allowed_actions": ["design", "mermaid", "recommend"], "can_deploy": False},
        "DeveloperAgent": {"allowed_actions": ["synthesize_hcl", "refactor"], "can_deploy": False},
        "SecurityReviewer": {"allowed_actions": ["checkov_scan", "opa_evaluate", "patch"], "can_deploy": False},
        "FinOpsSpecialist": {"allowed_actions": ["infracost_estimate", "right_size"], "can_deploy": False},
        "DeploymentSpecialist": {"allowed_actions": ["terraform_apply", "terraform_destroy"], "can_deploy": True},
        "GitOpsCoordinator": {"allowed_actions": ["create_branch", "open_pr", "merge_pr"], "can_deploy": True}
    }

    @classmethod
    def calculate_risk_score(cls, hcl_code: str, estimated_cost: float = 0.0) -> Dict[str, Any]:
        """
        Calculates a composite risk score (0 - 100) based on infrastructure blast radius,
        destructive statements, network exposure, and IAM power.
        """
        score = 10.0  # Base risk
        factors = []

        lower = hcl_code.lower()

        # 1. Check for unrestricted ingress / public routing
        if "0.0.0.0/0" in lower:
            score += 25.0
            factors.append("Unrestricted 0.0.0.0/0 public CIDR ingress detected (+25)")

        # 2. Check for administrative IAM privileges
        if '"*"' in lower or "'*'" in lower or "administratoraccess" in lower:
            score += 30.0
            factors.append("Broad IAM wildcard policy or Admin access configured (+30)")

        # 3. Check for destructive deletions or unencrypted databases
        if "prevent_destroy = false" in lower:
            score += 15.0
            factors.append("Deletion protection disabled (+15)")
        if "storage_encrypted = false" in lower or "encrypted = false" in lower:
            score += 20.0
            factors.append("Unencrypted storage explicitly configured (+20)")

        # 4. Cost magnitude impact
        if estimated_cost > 500.0:
            score += 15.0
            factors.append(f"High financial expenditure projected (${estimated_cost}/mo) (+15)")

        score = min(100.0, round(score, 1))

        risk_level = "LOW"
        if score >= 70.0:
            risk_level = "CRITICAL"
        elif score >= 45.0:
            risk_level = "HIGH"
        elif score >= 25.0:
            risk_level = "MEDIUM"

        return {
            "risk_score": score,
            "risk_level": risk_level,
            "risk_factors": factors,
            "can_auto_apply": score < 40.0
        }

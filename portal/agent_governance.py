import re
from typing import Dict, List, Any, Optional

class AgentGovernanceFramework:
    """
    AI Agent Governance & Multi-Dimensional Risk Scoring Framework.
    Evaluates infrastructure plans across 5 distinct risk axes:
    Security, Financial, Availability, Data Loss, and Compliance.
    """

    AGENT_PERMISSIONS = {
        "ArchitectAgent": {"allowed_actions": ["design", "mermaid", "recommend"], "can_deploy": False},
        "DeveloperAgent": {"allowed_actions": ["synthesize_hcl", "refactor"], "can_deploy": False},
        "SecurityReviewer": {"allowed_actions": ["checkov_scan", "opa_evaluate", "patch"], "can_deploy": False},
        "FinOpsSpecialist": {"allowed_actions": ["infracost_estimate", "right_size"], "can_deploy": False},
        "DeploymentSpecialist": {"allowed_actions": ["terraform_apply", "terraform_destroy"], "can_deploy": True},
        "GitOpsCoordinator": {"allowed_actions": ["create_branch", "open_pr", "merge_pr"], "can_deploy": True}
    }

    # Weight distribution across the 5 risk dimensions
    DIMENSION_WEIGHTS = {
        "security": 0.30,
        "financial": 0.20,
        "availability": 0.20,
        "data_loss": 0.20,
        "compliance": 0.10
    }

    @classmethod
    def calculate_risk_score(
        cls,
        hcl_code: str,
        estimated_cost: float = 0.0,
        cost_increase_pct: float = 0.0,
        environment: str = "staging"
    ) -> Dict[str, Any]:
        """
        Calculates a 5-Dimensional Risk Matrix and composite score (0 - 100).
        """
        lower = hcl_code.lower()
        env = environment.lower()
        is_prod = env in ["prod", "production"]

        # Base scores per dimension (10.0 is baseline hygiene)
        dim_scores = {
            "security": 10.0,
            "financial": 10.0,
            "availability": 10.0,
            "data_loss": 10.0,
            "compliance": 10.0
        }
        factors = []
        hard_block_reasons = []

        # ── 1. Security Risk Dimension ──────────────────────────────
        if "0.0.0.0/0" in lower:
            # Check if management ports (22, 3389) are open
            if "port = 22" in lower or "from_port = 22" in lower or "to_port = 22" in lower:
                dim_scores["security"] += 50.0
                hard_block_reasons.append("Hard Block: Open SSH (port 22) to 0.0.0.0/0 is strictly prohibited.")
            elif "port = 3389" in lower or "from_port = 3389" in lower:
                dim_scores["security"] += 50.0
                hard_block_reasons.append("Hard Block: Open RDP (port 3389) to 0.0.0.0/0 is strictly prohibited.")
            else:
                dim_scores["security"] += 30.0
                factors.append("Unrestricted 0.0.0.0/0 public CIDR ingress detected (+30 Security)")

        if '"*"' in lower or "'*'" in lower or "administratoraccess" in lower:
            dim_scores["security"] += 45.0
            factors.append("Broad IAM wildcard policy or Full Admin privileges detected (+45 Security)")
            if is_prod:
                hard_block_reasons.append("Hard Block: Wildcard Administrator IAM access in production environment.")

        # ── 2. Financial Risk Dimension ─────────────────────────────
        if estimated_cost > 1000.0:
            dim_scores["financial"] += 50.0
            factors.append(f"Critical financial spend projected (${estimated_cost}/mo) (+50 Financial)")
        elif estimated_cost > 500.0:
            dim_scores["financial"] += 30.0
            factors.append(f"High financial expenditure projected (${estimated_cost}/mo) (+30 Financial)")
        elif estimated_cost > 250.0:
            dim_scores["financial"] += 15.0
            factors.append(f"Moderate financial expenditure (${estimated_cost}/mo) (+15 Financial)")

        if cost_increase_pct > 30.0:
            dim_scores["financial"] += 35.0
            factors.append(f"Cost spike of {cost_increase_pct:.1f}% exceeds 30% financial threshold (+35 Financial)")
        elif cost_increase_pct > 20.0:
            dim_scores["financial"] += 20.0
            factors.append(f"Cost increase of {cost_increase_pct:.1f}% exceeds 20% threshold (+20 Financial)")

        # ── 3. Availability Risk Dimension ──────────────────────────
        if is_prod and "multi_az = false" in lower:
            dim_scores["availability"] += 40.0
            factors.append("Production resource configured without Multi-AZ redundancy (+40 Availability)")
        if "node_group" in lower and ("min_size = 0" in lower or "desired_size = 0" in lower):
            dim_scores["availability"] += 45.0
            factors.append("Kubernetes node pool scaled to 0 capacity (+45 Availability)")

        # ── 4. Data Loss Risk Dimension ─────────────────────────────
        if "prevent_destroy = false" in lower:
            dim_scores["data_loss"] += 30.0
            factors.append("Deletion protection explicitly disabled (+30 Data Loss)")
        if "storage_encrypted = false" in lower or "encrypted = false" in lower:
            dim_scores["data_loss"] += 35.0
            dim_scores["security"] += 25.0
            factors.append("Unencrypted persistent storage explicitly configured (+35 Data Loss)")

        # Check for production database destruction
        db_keywords = ["aws_db_instance", "azurerm_postgresql_server", "google_sql_database_instance"]
        if is_prod and any(db in lower for db in db_keywords):
            if "destroy" in lower or "deletion_protection = false" in lower:
                dim_scores["data_loss"] += 60.0
                hard_block_reasons.append("Hard Block: Production database destruction or unprotected deletion detected.")

        # Check for state bucket tampering
        if any(x in lower for x in ["tfstate", "terraform-state", "tofu-state"]):
            if "destroy" in lower or "force_destroy = true" in lower:
                dim_scores["data_loss"] += 60.0
                hard_block_reasons.append("Hard Block: Remote state storage bucket deletion or force_destroy detected.")

        # ── 5. Compliance Risk Dimension ────────────────────────────
        if is_prod and "tags" not in lower and "default_tags" not in lower:
            dim_scores["compliance"] += 25.0
            factors.append("Missing mandatory enterprise tags in production (+25 Compliance)")

        # Cap dimensional scores at 100.0
        for k in dim_scores:
            dim_scores[k] = min(100.0, round(dim_scores[k], 1))

        # Calculate weighted composite score
        composite_score = sum(dim_scores[dim] * cls.DIMENSION_WEIGHTS[dim] for dim in dim_scores)
        composite_score = min(100.0, round(composite_score, 1))

        # Determine overall risk level based on composite score AND max dimensional severity
        max_dim_score = max(dim_scores.values()) if dim_scores else composite_score
        risk_level = "LOW"
        if composite_score >= 70.0 or len(hard_block_reasons) > 0 or max_dim_score >= 75.0:
            risk_level = "CRITICAL"
        elif composite_score >= 45.0 or max_dim_score >= 50.0:
            risk_level = "HIGH"
        elif composite_score >= 25.0 or max_dim_score >= 30.0:
            risk_level = "MEDIUM"

        has_hard_blocks = len(hard_block_reasons) > 0
        can_auto_apply = composite_score < 40.0 and max_dim_score < 50.0 and not has_hard_blocks and not is_prod

        return {
            "composite_risk_score": composite_score,
            "risk_score": composite_score,  # Backwards compatibility
            "risk_level": risk_level,
            "dimensional_scores": dim_scores,
            "risk_factors": factors,
            "hard_block_triggered": has_hard_blocks,
            "hard_block_reasons": hard_block_reasons,
            "can_auto_apply": can_auto_apply,
            "environment": environment
        }

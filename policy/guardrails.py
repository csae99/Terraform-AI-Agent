import os
import re
from typing import Dict, List, Any, Optional

class EnterpriseGuardrails:
    """
    Organization-level Policy Guardrail Enforcer & Hard Block Engine.
    Evaluates infrastructure blueprints against tenant constraints:
    hard blocks, region whitelisting, budget maximums, prohibited services, and mandatory tags.
    """

    DEFAULT_ALLOWED_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
    DEFAULT_MANDATORY_TAGS = ["Environment", "Owner", "ManagedBy"]
    DEFAULT_BANNED_RESOURCES = ["aws_iam_user_login_profile"]

    # Strict hard block rules that unconditionally halt autonomous apply
    HARD_BLOCKS = {
        "production_db_destroy": {
            "title": "Production Database Deletion",
            "description": "Destruction or deletion protection disablement on production database resources is strictly blocked."
        },
        "state_bucket_deletion": {
            "title": "Remote State Bucket Deletion",
            "description": "Deletion or force_destroy on Terraform/OpenTofu remote state buckets is strictly blocked."
        },
        "open_management_ports": {
            "title": "Unrestricted SSH / RDP Access",
            "description": "Opening port 22 (SSH) or 3389 (RDP) to 0.0.0.0/0 is strictly blocked."
        },
        "wildcard_admin_iam": {
            "title": "Wildcard Admin IAM Privilege",
            "description": "Granting Action: '*' and Resource: '*' IAM policies in production is strictly blocked."
        }
    }

    @classmethod
    def evaluate_guardrails(
        cls,
        hcl_code: str,
        budget: float,
        allowed_regions: Optional[List[str]] = None,
        max_budget_cap: float = 1000.0,
        banned_resources: Optional[List[str]] = None,
        environment: str = "staging"
    ) -> Dict[str, Any]:
        """
        Enforces organization-wide guardrails and hard blocks on generated IaC configurations.
        """
        regions = allowed_regions or cls.DEFAULT_ALLOWED_REGIONS
        banned = banned_resources or cls.DEFAULT_BANNED_RESOURCES
        violations = []
        hard_blocks_triggered = []
        lower = hcl_code.lower()
        env = environment.lower()
        is_prod = env in ["prod", "production"]

        # ── 1. Hard Block: Production Database Destruction ───────────
        db_types = ["aws_db_instance", "aws_rds_cluster", "azurerm_postgresql_server", "azurerm_mssql_database", "google_sql_database_instance"]
        if is_prod and any(db in lower for db in db_types):
            if "prevent_destroy = false" in lower or "deletion_protection = false" in lower:
                hard_blocks_triggered.append("HARD BLOCK: Attempted to disable deletion protection on a production database.")

        # ── 2. Hard Block: Remote State Storage Bucket Deletion ───────
        if any(state_kw in lower for state_kw in ["tfstate", "terraform-state", "tofu-state"]):
            if "force_destroy = true" in lower or "prevent_destroy = false" in lower:
                hard_blocks_triggered.append("HARD BLOCK: Attempted to force_destroy or disable protection on a remote state storage bucket.")

        # ── 3. Hard Block: Open Management Ports (SSH 22 / RDP 3389) ───
        if "0.0.0.0/0" in lower:
            if "port = 22" in lower or "from_port = 22" in lower or "to_port = 22" in lower:
                hard_blocks_triggered.append("HARD BLOCK: Ingress rule exposes SSH port 22 to the public internet (0.0.0.0/0).")
            elif "port = 3389" in lower or "from_port = 3389" in lower:
                hard_blocks_triggered.append("HARD BLOCK: Ingress rule exposes RDP port 3389 to the public internet (0.0.0.0/0).")

        # ── 4. Hard Block: Wildcard Admin IAM ────────────────────────
        if is_prod and ('"administratoraccess"' in lower or ('"action": "*"' in lower and '"resource": "*"' in lower)):
            hard_blocks_triggered.append("HARD BLOCK: Full wildcard administrator IAM access ('*') detected in production.")

        # ── 5. Budget Boundary Check ─────────────────────────────────
        if budget > max_budget_cap:
            violations.append(f"Guardrail Violation: Requested budget (${budget}) exceeds maximum organization limit of ${max_budget_cap}.")

        # ── 6. Region Whitelist Check ────────────────────────────────
        region_match = re.search(r'region\s*=\s*"([^"]+)"', hcl_code)
        if region_match:
            detected_region = region_match.group(1)
            if detected_region not in regions:
                violations.append(f"Guardrail Violation: Cloud region '{detected_region}' is not in the organization allowed regions list: {regions}.")

        # ── 7. Banned Resource Check ─────────────────────────────────
        for b in banned:
            if f'resource "{b}"' in hcl_code or f"resource '{b}'" in hcl_code:
                violations.append(f"Guardrail Violation: Resource type '{b}' is prohibited by organization security policy.")

        # ── 8. Mandatory Tagging Check ───────────────────────────────
        if 'resource "' in hcl_code and 'tags' not in hcl_code and 'default_tags' not in hcl_code:
            violations.append(f"Guardrail Warning: IaC code is missing standard enterprise tags ({', '.join(cls.DEFAULT_MANDATORY_TAGS)}).")

        all_violations = hard_blocks_triggered + violations
        is_passed = len(all_violations) == 0

        return {
            "passed": is_passed,
            "violations_count": len(all_violations),
            "violations": all_violations,
            "hard_blocks_triggered": hard_blocks_triggered,
            "has_hard_blocks": len(hard_blocks_triggered) > 0,
            "allowed_regions": regions,
            "max_budget_cap": max_budget_cap,
            "environment": environment
        }

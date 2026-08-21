import os
import re
from typing import Dict, List, Any, Optional

class EnterpriseGuardrails:
    """
    Organization-level Policy Guardrail Enforcer.
    Evaluates infrastructure blueprints against tenant constraints:
    allowed cloud regions, budget maximums, prohibited services, and mandatory tags.
    """

    DEFAULT_ALLOWED_REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"]
    DEFAULT_MANDATORY_TAGS = ["Environment", "Owner", "ManagedBy"]
    DEFAULT_BANNED_RESOURCES = ["aws_iam_user_login_profile"]

    @classmethod
    def evaluate_guardrails(
        cls,
        hcl_code: str,
        budget: float,
        allowed_regions: Optional[List[str]] = None,
        max_budget_cap: float = 1000.0,
        banned_resources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Enforces organization-wide guardrails on the generated IaC configuration.
        """
        regions = allowed_regions or cls.DEFAULT_ALLOWED_REGIONS
        banned = banned_resources or cls.DEFAULT_BANNED_RESOURCES
        violations = []

        # 1. Budget Boundary Check
        if budget > max_budget_cap:
            violations.append(f"Guardrail Violation: Requested budget (${budget}) exceeds maximum organization limit of ${max_budget_cap}.")

        # 2. Region Whitelist Check
        region_match = re.search(r'region\s*=\s*"([^"]+)"', hcl_code)
        if region_match:
            detected_region = region_match.group(1)
            if detected_region not in regions:
                violations.append(f"Guardrail Violation: Cloud region '{detected_region}' is not in the organization allowed regions list: {regions}.")

        # 3. Banned Resource Check
        for b in banned:
            if f'resource "{b}"' in hcl_code or f"resource '{b}'" in hcl_code:
                violations.append(f"Guardrail Violation: Resource type '{b}' is prohibited by organization security policy.")

        # 4. Mandatory Tagging Check
        # Check if default_tags or tags block exists when resources are present
        if 'resource "' in hcl_code and 'tags' not in hcl_code and 'default_tags' not in hcl_code:
            violations.append(f"Guardrail Warning: IaC code is missing standard enterprise tags ({', '.join(cls.DEFAULT_MANDATORY_TAGS)}).")

        return {
            "passed": len(violations) == 0,
            "violations_count": len(violations),
            "violations": violations,
            "allowed_regions": regions,
            "max_budget_cap": max_budget_cap
        }

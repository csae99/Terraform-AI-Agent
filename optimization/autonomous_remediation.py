import os
from typing import Dict, Any, Optional
from policy.opa_engine import OPAEngine
from portal.agent_governance import AgentGovernanceFramework

class AutonomousRemediationEngine:
    """
    Autonomous Infrastructure Remediation & Self-Healing Engine.
    Detects configuration drift or syntax failures, synthesizes an HCL patch,
    validates the patch with OPA and Risk Scoring, and autonomously applies safe remediations.
    """

    @classmethod
    def analyze_and_remediate(
        cls,
        current_hcl: str,
        detected_issue: str,
        issue_type: str = "security_vulnerability"
    ) -> Dict[str, Any]:
        """
        Synthesizes and evaluates a patch to autonomously remediate the detected issue.
        """
        patch_hcl = current_hcl
        remediation_actions = []

        # 1. Remediate unencrypted S3
        if "s3" in detected_issue.lower() and ("encrypt" in detected_issue.lower() or "public" in detected_issue.lower()):
            # Find existing bucket names
            import re
            bucket_matches = re.findall(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"', patch_hcl)
            target_bucket = bucket_matches[0] if bucket_matches else "data_store"

            # Set inline flags if present
            patch_hcl = re.sub(
                r'(resource\s+"aws_s3_bucket"\s+"[^"]+"\s*\{)',
                r'\1\n  block_public_acls = true\n  encrypted = true',
                patch_hcl
            )

            if "aws_s3_bucket_server_side_encryption_configuration" not in patch_hcl:
                patch_hcl += f"""
resource "aws_s3_bucket_server_side_encryption_configuration" "{target_bucket}_sse" {{
  bucket = "{target_bucket}"
  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}
"""
                remediation_actions.append("Injected server-side encryption configuration (AES256).")

            if "aws_s3_bucket_public_access_block" not in patch_hcl:
                patch_hcl += f"""
resource "aws_s3_bucket_public_access_block" "{target_bucket}_pab" {{
  bucket = "{target_bucket}"
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}
"""
                remediation_actions.append("Injected S3 Public Access Block guardrail.")

        # 2. Remediate broad security group ingress
        elif "security group" in detected_issue.lower() or "0.0.0.0/0" in detected_issue:
            patch_hcl = patch_hcl.replace('cidr_blocks = ["0.0.0.0/0"]', 'cidr_blocks = ["10.0.0.0/16"]')
            remediation_actions.append("Restricted open 0.0.0.0/0 ingress to private VPC CIDR (10.0.0.0/16).")

        # 3. Evaluate remediated patch with OPA & Risk Scoring
        opa_eval = OPAEngine.evaluate_compliance(patch_hcl, pack="soc2")
        risk_eval = AgentGovernanceFramework.calculate_risk_score(patch_hcl)

        is_safe_to_auto_apply = opa_eval["allow"] and risk_eval["risk_score"] < 40.0

        return {
            "remediation_status": "AUTO_REMEDIATED" if is_safe_to_auto_apply else "REQUIRES_HUMAN_APPROVAL",
            "issue_detected": detected_issue,
            "actions_taken": remediation_actions,
            "remediated_hcl": patch_hcl,
            "opa_compliance_passed": opa_eval["allow"],
            "remediated_compliance_score": opa_eval["compliance_score_percent"],
            "post_remediation_risk_score": risk_eval["risk_score"],
            "auto_applied": is_safe_to_auto_apply
        }

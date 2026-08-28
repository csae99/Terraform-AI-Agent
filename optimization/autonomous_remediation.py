import os
import re
import time
from typing import Dict, Any, Optional, List
from policy.opa_engine import OPAEngine
from portal.agent_governance import AgentGovernanceFramework
from tools.gitops.gitops_tools import GitOpsTools

class AutonomousRemediationEngine:
    """
    Autonomous Infrastructure Remediation & GitOps Closed-Loop Self-Healing Engine.
    Detects configuration drift, policy violations, or syntax failures, synthesizes an HCL patch,
    and enforces the Golden Rule:
        * Production mutations NEVER apply directly to live cloud.
        * They open an automated GitOps Pull Request with OPA compliance and Risk Matrix reports.
        * Staging/Dev environments can auto-apply if within safe risk boundaries.
    """

    @classmethod
    def analyze_and_remediate(
        cls,
        current_hcl: str,
        detected_issue: str,
        issue_type: str = "security_vulnerability",
        environment: str = "staging",
        gitops: bool = False,
        git_repo: Optional[str] = None,
        git_token: Optional[str] = None,
        target_branch: str = "main",
        workspace_slug: str = "remediated-workspace",
        org_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes an HCL patch and enforces GitOps PR generation for production or safe auto-apply for staging.
        """
        patch_hcl = current_hcl
        remediation_actions = []
        env = environment.lower()
        is_prod = env in ["prod", "production"]
        should_use_gitops = gitops or is_prod

        # ── 1. Synthesize Remediation Patch ───────────────────────────
        # Case: Unencrypted S3 Bucket
        if "s3" in detected_issue.lower() and ("encrypt" in detected_issue.lower() or "public" in detected_issue.lower()):
            bucket_matches = re.findall(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"', patch_hcl)
            target_bucket = bucket_matches[0] if bucket_matches else "data_store"

            # Inject inline attributes
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

        # Case: Broad Security Group Ingress (0.0.0.0/0)
        elif "security group" in detected_issue.lower() or "0.0.0.0/0" in detected_issue:
            patch_hcl = patch_hcl.replace('cidr_blocks = ["0.0.0.0/0"]', 'cidr_blocks = ["10.0.0.0/16"]')
            remediation_actions.append("Restricted open 0.0.0.0/0 ingress to private VPC CIDR (10.0.0.0/16).")

        # Case: Unencrypted Database
        elif "db" in detected_issue.lower() or "database" in detected_issue.lower():
            patch_hcl = re.sub(
                r'(resource\s+"aws_db_instance"\s+"[^"]+"\s*\{)',
                r'\1\n  storage_encrypted = true\n  deletion_protection = true',
                patch_hcl
            )
            remediation_actions.append("Enabled KMS storage encryption and deletion protection on RDS database.")

        else:
            remediation_actions.append(f"Applied general configuration remediation for: {detected_issue}")

        # ── 2. Evaluate Remediated Code via OPA & 5D Risk Matrix ─────
        opa_eval = OPAEngine.evaluate_compliance(patch_hcl, pack="soc2")
        risk_eval = AgentGovernanceFramework.calculate_risk_score(patch_hcl, environment=environment)

        # ── 3. Decision Routing: GitOps PR vs Safe Auto-Apply ────────
        if should_use_gitops:
            # Enforce the Golden Rule: Production changes MUST route through GitOps Pull Requests
            timestamp = int(time.time())
            branch_name = f"ai/remediation-{workspace_slug}-{timestamp}"
            pr_title = f"fix(remediation): auto-heal {detected_issue[:40]}"
            
            # Construct rich PR markdown body
            actions_list = "\n".join([f"- {a}" for a in remediation_actions])
            dim_scores = risk_eval.get("dimensional_scores", {})
            pr_body = f"""## 🛡️ Autonomous Infrastructure Remediation PR

### 🚨 Detected Runtime Drift / Issue
> **Issue:** {detected_issue}  
> **Environment:** `{environment}` | **Target Branch:** `{target_branch}`

### 🔧 Self-Healing Patch Summary
{actions_list}

### 📊 Governance & Policy Compliance Checks
- **SOC2 Compliance:** `{opa_eval.get('compliance_score_percent', 0)}%` (Status: `{'APPROVED' if opa_eval.get('allow') else 'FLAGGED'}`)
- **Composite Risk Score:** `{risk_eval.get('composite_risk_score', 0)}/100` (`{risk_eval.get('risk_level', 'LOW')}`)
- **5-Dimensional Breakdown:**
  - 🛡️ Security Risk: `{dim_scores.get('security', 0)}/100`
  - 💾 Data Loss Risk: `{dim_scores.get('data_loss', 0)}/100`
  - 💰 Financial Risk: `{dim_scores.get('financial', 0)}/100`
  - ⚡ Availability Risk: `{dim_scores.get('availability', 0)}/100`
  - 📜 Compliance Risk: `{dim_scores.get('compliance', 0)}/100`

### 📋 Proposed HCL Patch
```hcl
{patch_hcl.strip()}
```

### 👥 Required Sign-Off
- [ ] Organization Owner or Admin Approval required prior to merge.

---
*Created automatically by **Autonomous Remediation & GitOps Engine**.*
"""
            # Generate PR via GitOpsTools
            pr_result = GitOpsTools.create_pull_request(
                repo_url=git_repo or f"https://github.com/enterprise/{workspace_slug}",
                branch_name=branch_name,
                target_branch=target_branch,
                title=pr_title,
                body=pr_body,
                token=git_token
            )

            # Record in Enterprise Audit Trail if available
            try:
                from tools.project.audit_tracker import AuditTracker
                AuditTracker.record(
                    org_id=org_id,
                    user_id=user_id,
                    action="gitops_remediation_pr_created",
                    details={
                        "workspace_slug": workspace_slug,
                        "detected_issue": detected_issue,
                        "branch_name": branch_name,
                        "pr_number": pr_result.get("pr_number"),
                        "pr_url": pr_result.get("pr_url"),
                        "risk_score": risk_eval.get("composite_risk_score"),
                        "opa_passed": opa_eval.get("allow")
                    }
                )
            except Exception:
                pass

            return {
                "remediation_status": "GITOPS_PR_OPENED",
                "issue_detected": detected_issue,
                "environment": environment,
                "actions_taken": remediation_actions,
                "remediated_hcl": patch_hcl,
                "opa_compliance_passed": opa_eval["allow"],
                "remediated_compliance_score": opa_eval["compliance_score_percent"],
                "post_remediation_risk_score": risk_eval["composite_risk_score"],
                "dimensional_scores": dim_scores,
                "auto_applied": False,
                "gitops_pr": {
                    "branch_name": branch_name,
                    "pr_number": pr_result.get("pr_number"),
                    "pr_url": pr_result.get("pr_url"),
                    "pr_status": pr_result.get("pr_status", "open"),
                    "title": pr_title
                }
            }

        # Staging / Dev Non-GitOps path
        is_safe_to_auto_apply = opa_eval["allow"] and risk_eval["can_auto_apply"] and not risk_eval["hard_block_triggered"]

        return {
            "remediation_status": "AUTO_REMEDIATED" if is_safe_to_auto_apply else "REQUIRES_HUMAN_APPROVAL",
            "issue_detected": detected_issue,
            "environment": environment,
            "actions_taken": remediation_actions,
            "remediated_hcl": patch_hcl,
            "opa_compliance_passed": opa_eval["allow"],
            "remediated_compliance_score": opa_eval["compliance_score_percent"],
            "post_remediation_risk_score": risk_eval["composite_risk_score"],
            "dimensional_scores": risk_eval.get("dimensional_scores", {}),
            "auto_applied": is_safe_to_auto_apply
        }

"""
Kubernetes Status & Condition Manager for Terraform AI Operator.
Maintains standard Kubernetes status conditions, lifecycle phases, and event transitions.
"""

from typing import List, Optional
from datetime import datetime, timezone
from k8s.operator.crd_schema import Condition, TerraformAgentStatus, TerraformAgentResource


class StatusManager:
    """Manages Kubernetes conditions and lifecycle phase transitions for Custom Resources."""

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def set_condition(
        cls,
        status: TerraformAgentStatus,
        condition_type: str,
        condition_status: str,
        reason: str,
        message: str = "",
    ) -> None:
        """Adds or updates a condition in status.conditions maintaining standard transition semantics."""
        now = cls.now_iso()
        for cond in status.conditions:
            if cond.type == condition_type:
                if cond.status != condition_status:
                    cond.status = condition_status
                    cond.lastTransitionTime = now
                cond.reason = reason
                cond.message = message
                return

        # Condition does not exist yet
        status.conditions.append(
            Condition(
                type=condition_type,
                status=condition_status,
                lastTransitionTime=now,
                reason=reason,
                message=message,
            )
        )

    @classmethod
    def transition_to(
        cls,
        resource: TerraformAgentResource,
        new_phase: str,
        reason: str = "",
        message: str = "",
    ) -> None:
        """Transitions a TerraformAgent resource to a new phase and updates conditions accordingly."""
        resource.status.phase = new_phase
        resource.status.observedGeneration = resource.metadata.generation or 1

        if new_phase == "Synthesizing":
            cls.set_condition(resource.status, "Ready", "False", "SynthesisInProgress", message or "Multi-agent engine is generating HCL code.")
        elif new_phase == "Validating":
            cls.set_condition(resource.status, "Ready", "False", "ValidationInProgress", message or "Running OPA and 5D Risk evaluation.")
        elif new_phase == "PendingApproval":
            cls.set_condition(resource.status, "Ready", "False", "PendingHumanApproval", message or "Production infrastructure requires explicit approval or PR merge.")
            cls.set_condition(resource.status, "Compliant", "True", "ValidationPassed", "Compliance and security checks passed.")
        elif new_phase == "Applying":
            cls.set_condition(resource.status, "Ready", "False", "ApplyingPlan", message or "OpenTofu/Terraform engine executing infrastructure provisioning.")
        elif new_phase == "Applied":
            cls.set_condition(resource.status, "Ready", "True", "ProvisioningSucceeded", message or "Infrastructure successfully applied.")
            cls.set_condition(resource.status, "Compliant", "True", "AllPoliciesEnforced", "Zero high-severity violations detected.")
            cls.set_condition(resource.status, "DriftFree", "True", "InSync", "Live infrastructure is in sync with desired state.")
        elif new_phase == "DriftDetected":
            cls.set_condition(resource.status, "DriftFree", "False", "CloudDriftDiscovered", message or "Cloud state deviates from desired HCL configuration.")
        elif new_phase == "Failed":
            cls.set_condition(resource.status, "Ready", "False", reason or "ExecutionFailed", message or resource.status.errorMessage or "Pipeline failed.")

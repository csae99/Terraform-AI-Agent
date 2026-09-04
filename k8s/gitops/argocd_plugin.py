"""
ArgoCD GitOps Plugin & Custom Health Check Definitions.
Provides custom Lua health checks and manifest generator for ArgoCD integration.
"""

from typing import Dict, Any

# Standard ArgoCD Lua Health Check Script
ARGOCD_LUA_HEALTH_SCRIPT = """
hs = {}
if obj.status == nil then
  hs.status = "Progressing"
  hs.message = "Waiting for TerraformAgent status initialization"
  return hs
end

phase = obj.status.phase

if phase == "Applied" then
  hs.status = "Healthy"
  hs.message = "Infrastructure is fully applied and compliant."
  return hs
elseif phase == "Synthesizing" or phase == "Validating" or phase == "Applying" then
  hs.status = "Progressing"
  hs.message = "Reconciliation in progress (phase: " .. phase .. ")"
  return hs
elseif phase == "PendingApproval" then
  hs.status = "Suspended"
  hs.message = "Awaiting human approval for Pull Request: " .. (obj.status.activePR or "Pending")
  return hs
elseif phase == "DriftDetected" then
  hs.status = "Degraded"
  hs.message = "Cloud drift detected between real infrastructure and desired HCL."
  return hs
elseif phase == "Failed" then
  hs.status = "Degraded"
  hs.message = "TerraformAgent failed: " .. (obj.status.errorMessage or "Unknown error")
  return hs
end

hs.status = "Unknown"
hs.message = "Unknown phase: " .. (phase or "Nil")
return hs
"""


def evaluate_argocd_health(status_dict: Dict[str, Any]) -> Dict[str, str]:
    """
    Python equivalent of the ArgoCD Lua health check for testing and simulation.
    Maps TerraformAgent status.phase to ArgoCD health statuses:
    - Healthy
    - Progressing
    - Suspended
    - Degraded
    - Unknown
    """
    if not status_dict or "phase" not in status_dict:
        return {"status": "Progressing", "message": "Waiting for TerraformAgent status initialization"}

    phase = status_dict.get("phase")

    if phase == "Applied":
        return {"status": "Healthy", "message": "Infrastructure is fully applied and compliant."}

    if phase in ["Synthesizing", "Validating", "Applying"]:
        return {"status": "Progressing", "message": f"Reconciliation in progress (phase: {phase})"}

    if phase == "PendingApproval":
        pr = status_dict.get("activePR", "Pending")
        return {"status": "Suspended", "message": f"Awaiting human approval for Pull Request: {pr}"}

    if phase == "DriftDetected":
        return {"status": "Degraded", "message": "Cloud drift detected between real infrastructure and desired HCL."}

    if phase == "Failed":
        err = status_dict.get("errorMessage", "Unknown error")
        return {"status": "Degraded", "message": f"TerraformAgent failed: {err}"}

    return {"status": "Unknown", "message": f"Unknown phase: {phase}"}


def generate_argocd_cm_patch() -> Dict[str, Any]:
    """Generates the ArgoCD ConfigMap snippet (argocd-cm) to install the custom health check."""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "argocd-cm",
            "namespace": "argocd",
            "labels": {
                "app.kubernetes.io/part-of": "argocd"
            }
        },
        "data": {
            "resource.customizations.health.platform.terraform-ai.io_TerraformAgent": ARGOCD_LUA_HEALTH_SCRIPT.strip()
        }
    }

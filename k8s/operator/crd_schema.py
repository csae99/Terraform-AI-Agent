"""
Kubernetes Custom Resource Definitions (CRD) Pydantic Schemas.
Enforces strict type safety and schema validation matching the OpenAPI v3 CRD YAML manifests.
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime, timezone
from pydantic import BaseModel, Field, ConfigDict


# ==========================================
# Common Kubernetes Metadata & Condition
# ==========================================

class ObjectMeta(BaseModel):
    name: str
    namespace: Optional[str] = "default"
    labels: Optional[Dict[str, str]] = Field(default_factory=dict)
    annotations: Optional[Dict[str, str]] = Field(default_factory=dict)
    creationTimestamp: Optional[str] = None
    generation: Optional[int] = 1


class Condition(BaseModel):
    type: str
    status: Literal["True", "False", "Unknown"]
    lastTransitionTime: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    reason: Optional[str] = "Reconciled"
    message: Optional[str] = ""


# ==========================================
# 1. TerraformAgent CRD Schema
# ==========================================

class GovernanceSpec(BaseModel):
    maxBudgetMonthlyUSD: Optional[float] = 1000.0
    compliancePack: Literal["cis_aws_foundations", "soc2_type2", "hipaa_security", "standard"] = "cis_aws_foundations"
    riskThreshold: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"


class GitOpsSpec(BaseModel):
    targetRepo: Optional[str] = "https://github.com/company/infra-fleet.git"
    targetBranch: Optional[str] = "main"
    autoHealDrift: Optional[bool] = False
    createPullRequest: Optional[bool] = True


class StateBackendSpec(BaseModel):
    provider: Literal["s3", "azurerm", "gcs", "local"] = "s3"
    stateBucket: Optional[str] = "terraform-remote-state-store"
    lockTable: Optional[str] = "terraform-locks"
    region: Optional[str] = "us-east-1"


class TerraformAgentSpec(BaseModel):
    prompt: str = Field(..., description="Natural language infrastructure requirement")
    engine: Literal["opentofu", "terraform"] = "opentofu"
    environment: Literal["dev", "staging", "production"] = "dev"
    governance: GovernanceSpec = Field(default_factory=GovernanceSpec)
    gitops: GitOpsSpec = Field(default_factory=GitOpsSpec)
    stateBackend: StateBackendSpec = Field(default_factory=StateBackendSpec)


class TerraformAgentStatus(BaseModel):
    phase: Literal[
        "Pending",
        "Synthesizing",
        "Validating",
        "PendingApproval",
        "Applying",
        "Applied",
        "DriftDetected",
        "Failed",
    ] = "Pending"
    observedGeneration: int = 0
    lastRunDurationSec: Optional[float] = 0.0
    riskScore: Optional[str] = "0.0/100"
    riskLevel: Optional[str] = "LOW"
    infracostMonthlyUSD: Optional[float] = 0.0
    activePR: Optional[str] = None
    activeBranch: Optional[str] = None
    errorMessage: Optional[str] = None
    conditions: List[Condition] = Field(default_factory=list)


class TerraformAgentResource(BaseModel):
    apiVersion: str = "platform.terraform-ai.io/v1alpha1"
    kind: str = "TerraformAgent"
    metadata: ObjectMeta
    spec: TerraformAgentSpec
    status: TerraformAgentStatus = Field(default_factory=TerraformAgentStatus)


# ==========================================
# 2. PlatformProject CRD Schema
# ==========================================

class PlatformProjectSpec(BaseModel):
    organization: str
    tier: Literal["free", "starter", "professional", "enterprise"] = "professional"
    monthlyBudgetUSD: float = 5000.0
    allowedProviders: List[str] = Field(default_factory=lambda: ["aws", "azure", "gcp"])
    allowedRegions: List[str] = Field(default_factory=lambda: ["us-east-1", "us-west-2", "eu-west-1"])
    targetNamespace: Optional[str] = "default"


class PlatformProjectStatus(BaseModel):
    phase: Literal["Active", "BudgetExceeded", "Suspended"] = "Active"
    currentSpendUSD: float = 0.0
    activeWorkspacesCount: int = 0
    conditions: List[Condition] = Field(default_factory=list)


class PlatformProjectResource(BaseModel):
    apiVersion: str = "platform.terraform-ai.io/v1alpha1"
    kind: str = "PlatformProject"
    metadata: ObjectMeta
    spec: PlatformProjectSpec
    status: PlatformProjectStatus = Field(default_factory=PlatformProjectStatus)


# ==========================================
# 3. Workflow CRD Schema
# ==========================================

class WorkflowSpec(BaseModel):
    targetAgentRef: str
    pipelineMode: Literal["full_reconcile", "plan_only", "security_audit", "drift_heal"] = "full_reconcile"
    timeoutMinutes: int = 30
    concurrencyPolicy: Literal["Allow", "Forbid", "Replace"] = "Forbid"


class WorkflowStatus(BaseModel):
    phase: Literal["Pending", "Running", "Succeeded", "Failed", "Cancelled"] = "Pending"
    startTime: Optional[str] = None
    completionTime: Optional[str] = None
    durationSec: Optional[float] = 0.0
    stagesSummary: Optional[str] = "0/0"
    completedStages: List[str] = Field(default_factory=list)
    currentStage: Optional[str] = None
    error: Optional[str] = None


class WorkflowResource(BaseModel):
    apiVersion: str = "platform.terraform-ai.io/v1alpha1"
    kind: str = "Workflow"
    metadata: ObjectMeta
    spec: WorkflowSpec
    status: WorkflowStatus = Field(default_factory=WorkflowStatus)


# ==========================================
# 4. Policy CRD Schema
# ==========================================

class PolicySpec(BaseModel):
    ruleName: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "HIGH"
    enforcementAction: Literal["Deny", "Warn", "Audit"] = "Deny"
    regoSource: Optional[str] = None
    requiredTags: List[str] = Field(default_factory=lambda: ["Environment", "Owner", "CostCenter"])
    blockedResourceTypes: List[str] = Field(default_factory=list)


class PolicyStatus(BaseModel):
    active: bool = True
    violationCount: int = 0
    lastEvaluatedAt: Optional[str] = None
    failingResources: List[str] = Field(default_factory=list)


class PolicyResource(BaseModel):
    apiVersion: str = "platform.terraform-ai.io/v1alpha1"
    kind: str = "Policy"
    metadata: ObjectMeta
    spec: PolicySpec
    status: PolicyStatus = Field(default_factory=PolicyStatus)

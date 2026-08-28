import time
from typing import Dict, List, Any, Optional

class ApprovalEngine:
    """
    Dynamic Risk-Weighted Approval Gate & Operational Circuit Breaker Engine.
    Enforces multi-tier human sign-off rules and automatically trips circuit breakers
    on repeated failures, budget surges, or hard security violations.
    """

    # In-memory circuit breaker failure tracker: {workspace_id: consecutive_failure_count}
    _workspace_failure_counters: Dict[str, int] = {}
    _locked_workspaces: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def record_execution_outcome(cls, workspace_id: str, success: bool, reason: str = "") -> Dict[str, Any]:
        """
        Records the outcome of an agent execution to update failure counters and trigger circuit breakers.
        """
        ws_key = str(workspace_id or "default")
        if success:
            cls._workspace_failure_counters[ws_key] = 0
            return {"status": "HEALTHY", "consecutive_failures": 0}

        # Increment failure count
        cls._workspace_failure_counters[ws_key] = cls._workspace_failure_counters.get(ws_key, 0) + 1
        failures = cls._workspace_failure_counters[ws_key]

        # Trip Deployment Circuit Breaker if failures >= 3
        if failures >= 3:
            incident_id = f"INC-AUTO-FAIL-{ws_key}-{int(time.time())}"
            lock_record = {
                "incident_id": incident_id,
                "workspace_id": ws_key,
                "status": "LOCKED",
                "consecutive_failures": failures,
                "tripped_at": "2026-08-28T00:00:00Z",
                "lock_reason": f"Deployment Circuit Breaker Tripped: {failures} consecutive automated failures recorded ({reason})."
            }
            cls._locked_workspaces[ws_key] = lock_record
            return {
                "status": "CIRCUIT_BREAKER_TRIPPED",
                "consecutive_failures": failures,
                "incident": lock_record
            }

        return {"status": "WARNING", "consecutive_failures": failures}

    @classmethod
    def unlock_workspace(cls, workspace_id: str, operator_username: str) -> bool:
        """Unlocks a workspace that was tripped by the deployment circuit breaker."""
        ws_key = str(workspace_id or "default")
        if ws_key in cls._locked_workspaces:
            del cls._locked_workspaces[ws_key]
        cls._workspace_failure_counters[ws_key] = 0
        return True

    @classmethod
    def evaluate_approval_rules(
        cls,
        estimated_cost: float,
        risk_score: float,
        cost_increase_pct: float = 0.0,
        environment: str = "staging",
        user_role: str = "Developer",
        workspace_id: str = "default",
        has_hard_blocks: bool = False,
        dimensional_scores: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates environment, cost surge, blast radius risk, and circuit breakers
        to determine whether human sign-off is mandatory.
        """
        env = environment.lower()
        ws_key = str(workspace_id or "default")
        dim = dimensional_scores or {}
        requires_signoff = False
        circuit_breaker_tripped = False
        circuit_breaker_reasons = []
        reasons = []

        # ── 1. Check Deployment Circuit Breaker ─────────────────────
        if ws_key in cls._locked_workspaces:
            circuit_breaker_tripped = True
            requires_signoff = True
            lock = cls._locked_workspaces[ws_key]
            circuit_breaker_reasons.append(f"Deployment Circuit Breaker is active ({lock['incident_id']}): 3+ consecutive failures.")

        # ── 2. Check Security Circuit Breaker ───────────────────────
        if has_hard_blocks or dim.get("security", 0) >= 70.0 or dim.get("data_loss", 0) >= 70.0:
            circuit_breaker_tripped = True
            requires_signoff = True
            circuit_breaker_reasons.append("Security/Data Circuit Breaker Tripped: Critical risk or Hard Block violation detected.")

        # ── 3. Check Cost Circuit Breaker ───────────────────────────
        if cost_increase_pct > 30.0 or estimated_cost > 1000.0:
            circuit_breaker_tripped = True
            requires_signoff = True
            circuit_breaker_reasons.append(f"Cost Circuit Breaker Tripped: Projected spend surge exceeds 30% (+{cost_increase_pct:.1f}% / ${estimated_cost}).")

        # ── 4. Environment Policy ───────────────────────────────────
        if env in ["prod", "production"]:
            requires_signoff = True
            reasons.append("Production environment mutations require Owner or Admin approval.")

        # ── 5. Budget Threshold Policy ──────────────────────────────
        if estimated_cost > 250.0:
            requires_signoff = True
            reasons.append(f"Projected spend (${estimated_cost}/mo) exceeds auto-approval threshold of $250/mo.")

        # ── 6. Blast Radius Risk Policy ─────────────────────────────
        if risk_score > 60.0:
            requires_signoff = True
            reasons.append(f"Composite risk score ({risk_score}/100) indicates destructive or sensitive network alterations.")

        # Determine required approval role
        required_role = "Admin"
        if risk_score > 80.0 or env in ["prod", "production"] or circuit_breaker_tripped or has_hard_blocks:
            required_role = "Owner"

        return {
            "auto_approved": not requires_signoff and not circuit_breaker_tripped,
            "requires_human_signoff": requires_signoff,
            "circuit_breaker_tripped": circuit_breaker_tripped,
            "circuit_breaker_reasons": circuit_breaker_reasons,
            "required_role": required_role,
            "environment": environment,
            "estimated_cost": estimated_cost,
            "risk_score": risk_score,
            "reasons": reasons + circuit_breaker_reasons
        }

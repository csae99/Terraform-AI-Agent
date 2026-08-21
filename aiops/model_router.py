import os
from typing import Dict, Any

class IntelligentModelRouter:
    """
    Intelligent LLM Router & Cost Optimizer.
    Routes tasks to optimal AI models based on complexity, security sensitivity,
    and cost profiles.
    """

    MODEL_TIERS = {
        "fast_lean": {
            "model": "gemini/gemini-2.0-flash",
            "cost_per_1k": 0.0001,
            "best_for": ["Single resource HCL", "Markdown documentation", "Basic syntax validation"]
        },
        "balanced_reasoning": {
            "model": "gemini/gemini-1.5-pro",
            "cost_per_1k": 0.0012,
            "best_for": ["Modular architecture design", "FinOps optimization", "Multi-region VPCs"]
        },
        "frontier_expert": {
            "model": "openai/gpt-4o",
            "cost_per_1k": 0.0050,
            "best_for": ["Multi-Agent Debate", "Complex self-healing root cause analysis", "Zero-day vulnerability remediation"]
        }
    }

    @classmethod
    def route_task(cls, prompt: str, task_type: str = "general") -> Dict[str, Any]:
        """
        Selects the most cost-effective and capable model for the given task.
        """
        lower = prompt.lower()
        
        # Determine complexity
        is_complex = any(k in lower for k in ["kubernetes", "eks", "aks", "cluster", "peering", "transit_gateway", "debate", "remediation"])
        is_security_critical = any(k in lower for k in ["vault", "kms", "pci", "hipaa", "soc2", "iam_policy"])

        if is_security_critical or task_type == "debate":
            tier = "frontier_expert"
            reason = "Security-critical architecture or multi-agent debate requires frontier reasoning."
        elif is_complex or task_type == "architecture":
            tier = "balanced_reasoning"
            reason = "Modular architecture requires balanced reasoning model."
        else:
            tier = "fast_lean"
            reason = "Standard IaC template request routed to fast, cost-effective model."

        selected = cls.MODEL_TIERS[tier]
        return {
            "selected_tier": tier,
            "model_name": os.getenv("ACTIVE_ROUTED_MODEL", selected["model"]),
            "cost_profile_per_1k": selected["cost_per_1k"],
            "routing_reason": reason
        }

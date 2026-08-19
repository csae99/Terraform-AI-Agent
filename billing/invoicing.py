import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from billing.usage_tracking import BillingTracker

class InvoiceGenerator:
    """
    Generates cost attribution statements and monthly invoice summaries.
    """

    @classmethod
    def generate_monthly_statement(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """Generates a monthly billing and cost attribution summary."""
        usage_data = BillingTracker.get_usage_summary(user_id=user_id, org_id=org_id)
        sub = usage_data["subscription"]
        usage = usage_data["usage"]

        # Base plan fee
        from billing.stripe_service import StripeBillingService
        plan_meta = StripeBillingService.PLANS.get(sub["plan"], StripeBillingService.PLANS["free"])
        base_fee = float(plan_meta["price_monthly"])

        total_invoiced = round(base_fee, 2)

        return {
            "invoice_id": f"INV-{datetime.utcnow().strftime('%Y%m')}-{org_id or user_id or 101}",
            "period": datetime.utcnow().strftime("%B %Y"),
            "generated_at": datetime.utcnow().isoformat(),
            "subscription": {
                "plan_name": plan_meta["name"],
                "plan_tier": sub["plan"],
                "status": sub["status"],
                "base_monthly_fee_usd": base_fee
            },
            "consumption": {
                "runs_executed": usage["total_runs"],
                "monthly_limit": sub["monthly_limit"],
                "total_tokens": usage["total_tokens"],
                "ai_cost_incurred_usd": usage["total_ai_cost_usd"],
                "compute_seconds": usage["total_compute_seconds"],
                "compute_cost_incurred_usd": usage["total_compute_cost_usd"],
                "platform_cost_incurred_usd": usage["total_platform_cost_usd"],
                "infra_projected_spend_usd": usage["total_infra_monthly_projected_usd"]
            },
            "line_items": [
                {
                    "description": f"Subscription Tier: {plan_meta['name']}",
                    "amount_usd": base_fee
                }
            ],
            "total_due_usd": total_invoiced,
            "recent_runs": usage_data["recent_records"]
        }

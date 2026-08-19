import os
import uuid
from typing import Dict, Any, Optional
from billing.usage_tracking import BillingTracker

class StripeBillingService:
    """
    Subscription Plans & Stripe Billing Service.
    Supports tier definition, mock checkout for development, and live Stripe integration.
    """

    PLANS = {
        "free": {
            "id": "free",
            "name": "Free Tier",
            "price_monthly": 0,
            "monthly_runs": 5,
            "features": [
                "5 infrastructure runs per month",
                "Personal workspace",
                "Basic self-healing (up to 2 rounds)",
                "Standard OpenTelemetry metrics",
                "HashiCorp Terraform runtime"
            ],
            "recommended": False
        },
        "pro": {
            "id": "pro",
            "name": "Pro Developer",
            "price_monthly": 29,
            "monthly_runs": 100,
            "features": [
                "100 infrastructure runs per month",
                "Full GitOps & Pull Request automation",
                "Advanced self-healing with LLM reflection",
                "OpenTofu & Terraform dual engine",
                "Pattern memory self-learning bank",
                "Priority worker execution queue"
            ],
            "recommended": True
        },
        "enterprise": {
            "id": "enterprise",
            "name": "Enterprise Team",
            "price_monthly": 199,
            "monthly_runs": -1,  # Unlimited
            "features": [
                "Unlimited infrastructure generation & applies",
                "Multi-tenant organizations & RBAC",
                "Team approval gates prior to live deployment",
                "Immutable enterprise audit logging",
                "One-click SOC2 compliance evidence export",
                "Dedicated concurrency queue & custom models (BYOK)"
            ],
            "recommended": False
        }
    }

    @classmethod
    def list_plans(cls) -> Dict[str, Any]:
        """Returns all subscription tiers and feature matrices."""
        return cls.PLANS

    @classmethod
    def create_checkout_session(cls, plan_id: str, user_id: Optional[int] = None, org_id: Optional[int] = None,
                                return_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a checkout session for plan upgrade.
        If STRIPE_SECRET_KEY is configured, initializes Stripe Checkout; otherwise generates a mock checkout.
        """
        plan = cls.PLANS.get(plan_id.lower())
        if not plan:
            raise ValueError(f"Unknown plan: '{plan_id}'. Choose from: free, pro, enterprise")

        stripe_key = os.environ.get("STRIPE_SECRET_KEY")

        if stripe_key and not stripe_key.startswith("mock_"):
            try:
                import stripe
                stripe.api_key = stripe_key
                # Live Stripe Checkout Session
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "usd",
                            "product_data": {"name": f"Terraform AI Agent - {plan['name']}"},
                            "unit_amount": int(plan["price_monthly"] * 100),
                            "recurring": {"interval": "month"}
                        },
                        "quantity": 1,
                    }],
                    mode="subscription",
                    success_url=return_url or "http://localhost:5000/?upgrade=success",
                    cancel_url=return_url or "http://localhost:5000/?upgrade=canceled",
                    metadata={"user_id": str(user_id or ""), "org_id": str(org_id or ""), "plan": plan_id}
                )
                return {"checkout_url": session.url, "session_id": session.id, "simulated": False}
            except Exception as e:
                # Fallback to simulated checkout
                pass

        # Simulated checkout for development/local demo
        BillingTracker.set_plan(plan_id, user_id=user_id, org_id=org_id)
        mock_id = f"cs_test_{str(uuid.uuid4())[:16]}"
        return {
            "checkout_url": return_url or "http://localhost:5000/?upgrade=success",
            "session_id": mock_id,
            "simulated": True,
            "message": f"Successfully upgraded account to {plan['name']} tier."
        }

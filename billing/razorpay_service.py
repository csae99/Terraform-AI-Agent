import os
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from billing.usage_tracking import BillingTracker
from billing.stripe_service import StripeBillingService

class RazorpayBillingService:
    """
    Razorpay Payment & Subscription Gateway.
    Supports Razorpay Order creation, UPI/Card checkout, and cryptographic signature verification.
    """

    # Price in INR conversion multiplier (approx 1 USD = 85 INR)
    USD_TO_INR_RATE = 85.0

    @classmethod
    def get_key_id(cls) -> Optional[str]:
        return os.environ.get("RAZORPAY_KEY_ID")

    @classmethod
    def get_key_secret(cls) -> Optional[str]:
        return os.environ.get("RAZORPAY_KEY_SECRET")

    @classmethod
    def create_order(cls, plan_id: str, user_id: Optional[int] = None, org_id: Optional[int] = None,
                     currency: str = "INR") -> Dict[str, Any]:
        """
        Creates a Razorpay Order for a subscription plan.
        Converts plan price to smallest currency unit (paise for INR, cents for USD).
        Includes anti-double-charging verification if user has an active entitlement window.
        """
        plan = StripeBillingService.PLANS.get(plan_id.lower())
        if not plan:
            raise ValueError(f"Unknown plan: '{plan_id}'. Choose from: free, pro, enterprise")

        # Anti-double-charging protection: check if active paid entitlement is still valid
        if plan_id.lower() != "free":
            sub = BillingTracker.get_or_create_subscription(user_id=user_id, org_id=org_id)
            if sub.get("is_within_paid_period") and (sub.get("paid_plan") == plan_id.lower() or (plan_id.lower() == "pro" and sub.get("paid_plan") == "enterprise")):
                restore_result = BillingTracker.restore_paid_plan(user_id=user_id, org_id=org_id)
                return {
                    "already_paid": True,
                    "restored": True,
                    "plan": plan_id.lower(),
                    "paid_until": sub.get("paid_until"),
                    "message": f"Active {plan_id.upper()} subscription restored! Valid until {sub.get('paid_until')[:10]}. No payment required."
                }

        if plan["price_monthly"] == 0:
            return BillingTracker.downgrade_subscription(cancel_at_period_end=True, user_id=user_id, org_id=org_id)

        price_usd = float(plan["price_monthly"])
        key_id = cls.get_key_id()
        key_secret = cls.get_key_secret()

        # Calculate amount in paise / cents
        if currency.upper() == "INR":
            amount_in_units = int(price_usd * cls.USD_TO_INR_RATE * 100)  # Amount in paise
        else:
            currency = "USD"
            amount_in_units = int(price_usd * 100)  # Amount in cents

        receipt_id = f"rcpt_{plan_id}_{org_id or user_id or '0'}_{uuid.uuid4().hex[:8]}"

        # If live Razorpay keys are present, use official SDK or REST API
        if key_id and key_secret and not key_id.startswith("rzp_test_placeholder"):
            # 1. Try official SDK first if installed
            try:
                import razorpay
                client = razorpay.Client(auth=(key_id, key_secret))
                order_data = {
                    "amount": amount_in_units,
                    "currency": currency,
                    "receipt": receipt_id,
                    "notes": {
                        "plan": plan_id,
                        "user_id": str(user_id or ""),
                        "org_id": str(org_id or "")
                    }
                }
                order = client.order.create(data=order_data)
                return {
                    "order_id": order["id"],
                    "amount": order["amount"],
                    "currency": order["currency"],
                    "key_id": key_id,
                    "plan_name": plan["name"],
                    "plan_id": plan_id,
                    "simulated": False
                }
            except ImportError:
                # 2. SDK not installed: fallback to direct HTTP Basic Auth REST API call
                try:
                    import requests
                    order_payload = {
                        "amount": amount_in_units,
                        "currency": currency,
                        "receipt": receipt_id,
                        "notes": {
                            "plan": plan_id,
                            "user_id": str(user_id or ""),
                            "org_id": str(org_id or "")
                        }
                    }
                    resp = requests.post(
                        "https://api.razorpay.com/v1/orders",
                        auth=(key_id, key_secret),
                        json=order_payload,
                        timeout=10
                    )
                    if resp.status_code in (200, 201):
                        order = resp.json()
                        return {
                            "order_id": order["id"],
                            "amount": order["amount"],
                            "currency": order["currency"],
                            "key_id": key_id,
                            "plan_name": plan["name"],
                            "plan_id": plan_id,
                            "simulated": False
                        }
                    else:
                        err_msg = f"Razorpay API error ({resp.status_code}): {resp.text}"
                        print(f"[Razorpay] {err_msg}")
                        raise RuntimeError(err_msg)
                except Exception as rest_e:
                    print(f"[Razorpay] REST order creation failed: {rest_e}")
                    raise
            except Exception as sdk_e:
                print(f"[Razorpay] SDK order creation failed: {sdk_e}")
                raise

        # Simulated order for development/testing when no API keys are provided
        mock_order_id = f"order_mock_{uuid.uuid4().hex[:14]}"
        return {
            "order_id": mock_order_id,
            "amount": amount_in_units,
            "currency": currency,
            "key_id": key_id or "rzp_test_simulated_key",
            "plan_name": plan["name"],
            "plan_id": plan_id,
            "simulated": True,
            "message": "Order created in simulation mode."
        }

    @classmethod
    def verify_payment_signature(cls, razorpay_order_id: str, razorpay_payment_id: str,
                                 razorpay_signature: str, plan_id: str,
                                 user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Verifies the cryptographic HMAC-SHA256 signature from Razorpay.
        On success, activates the upgraded subscription plan.
        """
        key_secret = cls.get_key_secret()

        now = datetime.utcnow()
        paid_until = now + timedelta(days=30)

        # If in simulated mode
        if razorpay_order_id.startswith("order_mock_") or not key_secret:
            BillingTracker.set_plan(
                plan_id, user_id=user_id, org_id=org_id,
                paid_until=paid_until,
                last_payment_id=razorpay_payment_id or f"pay_sim_{uuid.uuid4().hex[:8]}",
                last_payment_gateway="razorpay"
            )
            return {
                "verified": True,
                "simulated": True,
                "plan": plan_id,
                "paid_until": paid_until.isoformat(),
                "message": f"Simulated payment verified. Subscription upgraded to {plan_id.upper()} (valid for 30 days)."
            }

        # Cryptographic verification
        msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
        generated_signature = hmac.new(key_secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()

        if generated_signature == razorpay_signature:
            BillingTracker.set_plan(
                plan_id, user_id=user_id, org_id=org_id,
                paid_until=paid_until,
                last_payment_id=razorpay_payment_id,
                last_payment_gateway="razorpay"
            )
            return {
                "verified": True,
                "simulated": False,
                "plan": plan_id,
                "paid_until": paid_until.isoformat(),
                "payment_id": razorpay_payment_id,
                "message": f"Payment successfully verified! Upgraded to {plan_id.upper()} (valid until {paid_until.strftime('%b %d, %Y')})."
            }
        else:
            return {
                "verified": False,
                "error": "Invalid signature. Payment verification failed."
            }

import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from tools.project.tracker import Base, SessionLocal, UserModel, OrganizationModel

class UsageRecordModel(Base):
    """Stores granular resource usage per run."""
    __tablename__ = "usage_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    project_slug = Column(String, index=True)
    
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    ai_cost_usd = Column(Float, default=0.0)
    
    compute_seconds = Column(Float, default=0.0)
    compute_cost_usd = Column(Float, default=0.0)
    
    infra_monthly_cost = Column(Float, default=0.0)
    total_platform_cost_usd = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriptionModel(Base):
    """Stores subscription tier and monthly quotas per user or organization."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, unique=True)
    
    plan = Column(String, default="free")  # free, pro, enterprise
    status = Column(String, default="active")  # active, canceled, past_due
    
    runs_this_month = Column(Integer, default=0)
    monthly_limit = Column(Integer, default=5)  # 5 for free, 100 for pro, -1 for unlimited
    
    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    billing_cycle_start = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _init_billing_tables():
    """Ensure billing tables exist in database."""
    from sqlalchemy import inspect
    session = SessionLocal()
    try:
        db_engine = session.bind
        Base.metadata.create_all(bind=db_engine, tables=[UsageRecordModel.__table__, SubscriptionModel.__table__])
    except Exception as e:
        print(f"[Billing DB] Table initialization note: {e}")
    finally:
        session.close()

_init_billing_tables()


class BillingTracker:
    """
    Service for managing subscriptions, tracking usage records, and enforcing quotas.
    """

    PLAN_LIMITS = {
        "free": 5,
        "pro": 100,
        "enterprise": -1  # Unlimited
    }

    @classmethod
    def get_or_create_subscription(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """Retrieves active subscription or creates a default Free tier."""
        session = SessionLocal()
        try:
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            if not sub:
                plan = "enterprise" if org_id else "free"
                limit = cls.PLAN_LIMITS.get(plan, 5)
                sub = SubscriptionModel(
                    user_id=user_id if not org_id else None,
                    org_id=org_id,
                    plan=plan,
                    status="active",
                    runs_this_month=0,
                    monthly_limit=limit
                )
                session.add(sub)
                session.commit()
                session.refresh(sub)

            return {
                "id": sub.id,
                "user_id": sub.user_id,
                "org_id": sub.org_id,
                "plan": sub.plan,
                "status": sub.status,
                "runs_this_month": sub.runs_this_month,
                "monthly_limit": sub.monthly_limit,
                "unlimited": sub.monthly_limit == -1,
                "remaining_runs": "Unlimited" if sub.monthly_limit == -1 else max(0, sub.monthly_limit - sub.runs_this_month),
                "billing_cycle_start": sub.billing_cycle_start.isoformat() if sub.billing_cycle_start else ""
            }
        finally:
            session.close()

    @classmethod
    def check_quota(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Checks whether the user/org has remaining execution quota for the current billing cycle.
        Returns {"allowed": True/False, "plan": str, "used": int, "limit": int}
        """
        # Check if billing quota enforcement is globally bypassed via ENV
        if os.environ.get("ENFORCE_BILLING_QUOTAS", "false").lower() == "false":
            return {"allowed": True, "reason": "Quotas bypassed in dev/test mode"}

        sub = cls.get_or_create_subscription(user_id=user_id, org_id=org_id)
        if sub["unlimited"]:
            return {"allowed": True, "plan": sub["plan"], "used": sub["runs_this_month"], "limit": "Unlimited"}

        if sub["runs_this_month"] >= sub["monthly_limit"]:
            return {
                "allowed": False,
                "plan": sub["plan"],
                "used": sub["runs_this_month"],
                "limit": sub["monthly_limit"],
                "error": f"Monthly execution quota reached ({sub['runs_this_month']}/{sub['monthly_limit']}). Upgrade to Pro or Enterprise for additional capacity."
            }

        return {"allowed": True, "plan": sub["plan"], "used": sub["runs_this_month"], "limit": sub["monthly_limit"]}

    @classmethod
    def record_usage(cls, project_slug: str, prompt_tokens: int, completion_tokens: int,
                     ai_cost: float, compute_seconds: float, compute_cost: float,
                     infra_monthly_cost: float, user_id: Optional[int] = None, org_id: Optional[int] = None):
        """Records a single usage entry and increments monthly run count."""
        session = SessionLocal()
        try:
            total_tokens = prompt_tokens + completion_tokens
            total_platform_cost = round(ai_cost + compute_cost, 4)

            record = UsageRecordModel(
                user_id=user_id,
                org_id=org_id,
                project_slug=project_slug,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                ai_cost_usd=ai_cost,
                compute_seconds=compute_seconds,
                compute_cost_usd=compute_cost,
                infra_monthly_cost=infra_monthly_cost,
                total_platform_cost_usd=total_platform_cost
            )
            session.add(record)

            # Increment runs_this_month on subscription
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            if sub:
                sub.runs_this_month = (sub.runs_this_month or 0) + 1

            session.commit()
            return record.id
        finally:
            session.close()

    @classmethod
    def set_plan(cls, plan: str, user_id: Optional[int] = None, org_id: Optional[int] = None):
        """Upgrades or modifies subscription tier."""
        session = SessionLocal()
        try:
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            limit = cls.PLAN_LIMITS.get(plan.lower(), 5)

            if sub:
                sub.plan = plan.lower()
                sub.monthly_limit = limit
                sub.status = "active"
                sub.updated_at = datetime.utcnow()
            else:
                sub = SubscriptionModel(
                    user_id=user_id if not org_id else None,
                    org_id=org_id,
                    plan=plan.lower(),
                    status="active",
                    runs_this_month=0,
                    monthly_limit=limit
                )
                session.add(sub)

            session.commit()
            return cls.get_or_create_subscription(user_id=user_id, org_id=org_id)
        finally:
            session.close()

    @classmethod
    def get_usage_summary(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """Calculates aggregated usage metrics for the active account."""
        session = SessionLocal()
        try:
            query = session.query(UsageRecordModel)
            if org_id:
                records = query.filter(UsageRecordModel.org_id == org_id).all()
            elif user_id:
                records = query.filter(UsageRecordModel.user_id == user_id).all()
            else:
                records = query.all()

            total_runs = len(records)
            total_prompt_tokens = sum(r.prompt_tokens or 0 for r in records)
            total_completion_tokens = sum(r.completion_tokens or 0 for r in records)
            total_tokens = total_prompt_tokens + total_completion_tokens
            total_ai_cost = round(sum(r.ai_cost_usd or 0.0 for r in records), 4)
            total_compute_seconds = round(sum(r.compute_seconds or 0.0 for r in records), 2)
            total_compute_cost = round(sum(r.compute_cost_usd or 0.0 for r in records), 4)
            total_platform_cost = round(sum(r.total_platform_cost_usd or 0.0 for r in records), 4)
            total_infra_cost = round(sum(r.infra_monthly_cost or 0.0 for r in records), 2)

            sub = cls.get_or_create_subscription(user_id=user_id, org_id=org_id)

            return {
                "subscription": sub,
                "usage": {
                    "total_runs": total_runs,
                    "total_tokens": total_tokens,
                    "total_prompt_tokens": total_prompt_tokens,
                    "total_completion_tokens": total_completion_tokens,
                    "total_ai_cost_usd": total_ai_cost,
                    "total_compute_seconds": total_compute_seconds,
                    "total_compute_cost_usd": total_compute_cost,
                    "total_platform_cost_usd": total_platform_cost,
                    "total_infra_monthly_projected_usd": total_infra_cost
                },
                "recent_records": [
                    {
                        "id": r.id,
                        "project_slug": r.project_slug,
                        "tokens": r.total_tokens,
                        "ai_cost_usd": r.ai_cost_usd,
                        "compute_seconds": r.compute_seconds,
                        "compute_cost_usd": r.compute_cost_usd,
                        "platform_cost_usd": r.total_platform_cost_usd,
                        "created_at": r.created_at.isoformat() if r.created_at else ""
                    } for r in reversed(records[-15:])
                ]
            }
        finally:
            session.close()

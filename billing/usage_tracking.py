import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
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
    status = Column(String, default="active")  # active, canceled, past_due, canceling
    
    runs_this_month = Column(Integer, default=0)
    monthly_limit = Column(Integer, default=5)  # 5 for free, 100 for pro, -1 for unlimited
    
    # Paid entitlement lifecycle (anti-double-charging & graceful downgrade)
    paid_until = Column(DateTime, nullable=True)
    paid_plan = Column(String, nullable=True)  # Highest tier purchased (e.g. 'pro', 'enterprise')
    cancel_at_period_end = Column(Boolean, default=False)
    last_payment_gateway = Column(String, nullable=True)  # razorpay, stripe
    last_payment_id = Column(String, nullable=True)

    stripe_customer_id = Column(String, nullable=True)
    stripe_subscription_id = Column(String, nullable=True)
    
    billing_cycle_start = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _init_billing_tables():
    """Ensure billing tables exist in database and perform incremental migrations."""
    from sqlalchemy import inspect, text
    session = SessionLocal()
    try:
        db_engine = session.bind
        Base.metadata.create_all(bind=db_engine, tables=[UsageRecordModel.__table__, SubscriptionModel.__table__])
        # Auto-migrate existing subscriptions tables to include lifecycle columns
        inspector = inspect(db_engine)
        if "subscriptions" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("subscriptions")]
            new_columns = [
                ("paid_until", "TIMESTAMP"),
                ("paid_plan", "VARCHAR"),
                ("cancel_at_period_end", "BOOLEAN DEFAULT 0"),
                ("last_payment_gateway", "VARCHAR"),
                ("last_payment_id", "VARCHAR")
            ]
            with db_engine.connect() as conn:
                for col_name, col_type in new_columns:
                    if col_name not in columns:
                        try:
                            conn.execute(text(f"ALTER TABLE subscriptions ADD COLUMN {col_name} {col_type}"))
                            conn.commit()
                        except Exception as e:
                            print(f"[Billing DB] Column migration notice for {col_name}: {e}")
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
    def _check_expired_subscription(cls, session, user_id: Optional[int] = None, org_id: Optional[int] = None):
        """Transitions subscription to Free if cancel_at_period_end is active and paid_until has passed."""
        query = session.query(SubscriptionModel)
        if org_id:
            sub = query.filter(SubscriptionModel.org_id == org_id).first()
        elif user_id:
            sub = query.filter(SubscriptionModel.user_id == user_id).first()
        else:
            sub = None

        if sub and sub.cancel_at_period_end and sub.paid_until:
            if datetime.utcnow() > sub.paid_until:
                sub.plan = "free"
                sub.monthly_limit = cls.PLAN_LIMITS.get("free", 5)
                sub.cancel_at_period_end = False
                sub.status = "active"
                sub.updated_at = datetime.utcnow()
                session.commit()

    @classmethod
    def get_or_create_subscription(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """Retrieves active subscription or creates a default Free tier."""
        session = SessionLocal()
        try:
            cls._check_expired_subscription(session, user_id=user_id, org_id=org_id)
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            if not sub:
                plan = "free"
                limit = cls.PLAN_LIMITS.get(plan, 5)
                sub = SubscriptionModel(
                    user_id=user_id if not org_id else None,
                    org_id=org_id,
                    plan=plan,
                    status="active",
                    runs_this_month=0,
                    monthly_limit=limit,
                    cancel_at_period_end=False
                )
                session.add(sub)
                session.commit()
                session.refresh(sub)

            now = datetime.utcnow()
            is_within_paid_period = bool(sub.paid_until and sub.paid_until > now)

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
                "billing_cycle_start": sub.billing_cycle_start.isoformat() if sub.billing_cycle_start else "",
                "paid_until": sub.paid_until.isoformat() if sub.paid_until else "",
                "paid_plan": sub.paid_plan or "",
                "cancel_at_period_end": bool(sub.cancel_at_period_end),
                "is_within_paid_period": is_within_paid_period,
                "last_payment_gateway": sub.last_payment_gateway or "",
                "last_payment_id": sub.last_payment_id or ""
            }
        finally:
            session.close()

    @classmethod
    def check_quota(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Checks whether the user/org has remaining execution quota for the current billing cycle.
        Returns {"allowed": True/False, "plan": str, "used": int, "limit": int}
        """
        # Check if billing quota enforcement is globally bypassed via ENV (defaults to enabled)
        if os.environ.get("ENFORCE_BILLING_QUOTAS", "true").lower() in ("false", "0", "no"):
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
        if user_id is not None:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = None
        if org_id is not None:
            try:
                org_id = int(org_id)
            except (ValueError, TypeError):
                org_id = None

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

            # Increment runs_this_month on subscription (create default Free tier if not exists)
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            if not sub and (user_id or org_id):
                plan = "free"
                limit = cls.PLAN_LIMITS.get(plan, 5)
                sub = SubscriptionModel(
                    user_id=user_id if not org_id else None,
                    org_id=org_id,
                    plan=plan,
                    status="active",
                    runs_this_month=1,
                    monthly_limit=limit
                )
                session.add(sub)
            elif sub:
                sub.runs_this_month = (sub.runs_this_month or 0) + 1

            session.commit()
            return record.id
        finally:
            session.close()

    @classmethod
    def set_plan(cls, plan: str, user_id: Optional[int] = None, org_id: Optional[int] = None,
                 paid_until: Optional[datetime] = None, last_payment_id: Optional[str] = None,
                 last_payment_gateway: Optional[str] = None):
        """Upgrades or modifies subscription tier with entitlement tracking."""
        session = SessionLocal()
        try:
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            plan_name = plan.lower()
            limit = cls.PLAN_LIMITS.get(plan_name, 5)
            now = datetime.utcnow()

            if sub:
                sub.plan = plan_name
                sub.monthly_limit = limit
                sub.status = "active"
                sub.cancel_at_period_end = False
                if plan_name != "free":
                    sub.paid_plan = plan_name
                    if paid_until:
                        sub.paid_until = paid_until
                    elif not sub.paid_until or sub.paid_until < now:
                        sub.paid_until = now + timedelta(days=30)
                if last_payment_id:
                    sub.last_payment_id = last_payment_id
                if last_payment_gateway:
                    sub.last_payment_gateway = last_payment_gateway
                sub.updated_at = now
            else:
                effective_paid_until = paid_until or ((now + timedelta(days=30)) if plan_name != "free" else None)
                sub = SubscriptionModel(
                    user_id=user_id if not org_id else None,
                    org_id=org_id,
                    plan=plan_name,
                    status="active",
                    runs_this_month=0,
                    monthly_limit=limit,
                    paid_plan=plan_name if plan_name != "free" else None,
                    paid_until=effective_paid_until,
                    cancel_at_period_end=False,
                    last_payment_id=last_payment_id,
                    last_payment_gateway=last_payment_gateway
                )
                session.add(sub)

            session.commit()
            return cls.get_or_create_subscription(user_id=user_id, org_id=org_id)
        finally:
            session.close()

    @classmethod
    def downgrade_subscription(cls, cancel_at_period_end: bool = True, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Handles downgrading to the Free tier.
        If cancel_at_period_end is True (recommended):
            Retains current paid plan and remaining runs until paid_until.
            Sets cancel_at_period_end = True and status = 'canceling'.
        If cancel_at_period_end is False (immediate downgrade):
            Switches to free immediately (limit = 5), but preserves paid_until and paid_plan
            so user can restore at zero charge if they change their mind before paid_until.
        """
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
                return cls.get_or_create_subscription(user_id=user_id, org_id=org_id)

            now = datetime.utcnow()
            has_paid_period = bool(sub.paid_until and sub.paid_until > now)

            if cancel_at_period_end and has_paid_period:
                sub.cancel_at_period_end = True
                sub.status = "canceling"
                sub.updated_at = now
                session.commit()
                return {
                    "success": True,
                    "mode": "period_end",
                    "plan": sub.plan,
                    "cancel_at_period_end": True,
                    "paid_until": sub.paid_until.isoformat() if sub.paid_until else "",
                    "message": f"Your {sub.plan.upper()} subscription will remain active until {sub.paid_until.strftime('%b %d, %Y')}. You will not be charged again."
                }
            else:
                # Immediate downgrade
                sub.plan = "free"
                sub.monthly_limit = cls.PLAN_LIMITS.get("free", 5)
                sub.cancel_at_period_end = False
                sub.status = "active"
                sub.updated_at = now
                session.commit()
                return {
                    "success": True,
                    "mode": "immediate",
                    "plan": "free",
                    "cancel_at_period_end": False,
                    "paid_until": sub.paid_until.isoformat() if sub.paid_until else "",
                    "can_restore": has_paid_period,
                    "message": "Switched to Free tier immediately." + (f" Note: You can restore your Pro entitlement anytime before {sub.paid_until.strftime('%b %d, %Y')} at no extra charge." if has_paid_period else "")
                }
        finally:
            session.close()

    @classmethod
    def restore_paid_plan(cls, user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Restores a previously paid plan if paid_until is still in the future.
        Guarantees users are never double-charged for an active cycle!
        """
        session = SessionLocal()
        try:
            query = session.query(SubscriptionModel)
            if org_id:
                sub = query.filter(SubscriptionModel.org_id == org_id).first()
            elif user_id:
                sub = query.filter(SubscriptionModel.user_id == user_id).first()
            else:
                sub = None

            if not sub or not sub.paid_until or sub.paid_until <= datetime.utcnow():
                return {"restored": False, "reason": "No active paid entitlement found"}

            restore_tier = sub.paid_plan or "pro"
            limit = cls.PLAN_LIMITS.get(restore_tier, 100)

            sub.plan = restore_tier
            sub.monthly_limit = limit
            sub.cancel_at_period_end = False
            sub.status = "active"
            sub.updated_at = datetime.utcnow()
            session.commit()

            return {
                "restored": True,
                "plan": restore_tier,
                "paid_until": sub.paid_until.isoformat(),
                "monthly_limit": limit,
                "remaining_runs": "Unlimited" if limit == -1 else max(0, limit - sub.runs_this_month),
                "message": f"Welcome back! Restored your {restore_tier.upper()} plan without charge. Active until {sub.paid_until.strftime('%b %d, %Y')}."
            }
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

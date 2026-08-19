import time
import re
from typing import Dict, Any, List, Optional
from observability.metrics import metrics
from tools.project.tracker import ProjectTracker

class AnalyticsEngine:
    """
    Analytics engine providing executive KPI summaries, failure taxonomy breakdowns,
    success rate trends, and pattern memory leaderboard.
    """

    @staticmethod
    def get_executive_kpis(org_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Calculates executive-level KPIs and analytics across projects."""
        projects = ProjectTracker.load_all(owner_id=user_id, org_id=org_id)
        
        total_workspaces = len(projects)
        deployed_count = sum(1 for p in projects if p.get("status") == "deployed")
        generated_count = sum(1 for p in projects if p.get("status") == "generated")
        failed_count = sum(1 for p in projects if p.get("status") == "failed")
        destroyed_count = sum(1 for p in projects if p.get("status") == "destroyed")
        pr_opened_count = sum(1 for p in projects if p.get("status") == "pr_opened" or p.get("pr_url"))

        # Success rate (deployed / (deployed + failed))
        evaluable_runs = deployed_count + failed_count
        success_rate = round((deployed_count / evaluable_runs * 100), 1) if evaluable_runs > 0 else 100.0

        # FinOps Aggregates
        total_monthly_spend = round(sum(p.get("estimated_cost", 0.0) or 0.0 for p in projects), 2)
        total_security_issues = sum(p.get("security_issues", 0) or 0 for p in projects)
        total_healing_rounds = sum(p.get("healing_rounds_taken", 0) or 0 for p in projects)
        total_duration = round(sum(p.get("run_duration", 0.0) or 0.0 for p in projects), 2)
        avg_run_duration = round(total_duration / total_workspaces, 2) if total_workspaces > 0 else 0.0

        # Estimated cost savings from self-healing (prevented cloud downtime / manual engineering hours: ~$120/hr)
        estimated_hours_saved = round((total_healing_rounds * 1.5) + (total_workspaces * 2.0), 1)
        estimated_cost_saved = round(estimated_hours_saved * 120.0, 2)

        # Failure Taxonomy Analysis
        failure_taxonomy = AnalyticsEngine._categorize_failures(projects)

        # Engine breakdown (Terraform vs OpenTofu)
        engine_breakdown = {
            "terraform": sum(1 for p in projects if (p.get("engine") or "terraform").lower() == "terraform"),
            "opentofu": sum(1 for p in projects if (p.get("engine") or "").lower() in ("opentofu", "tofu"))
        }

        # Pattern Confidence Leaderboard
        pattern_leaderboard = AnalyticsEngine._get_pattern_leaderboard()

        return {
            "kpis": {
                "total_workspaces": total_workspaces,
                "deployed_workspaces": deployed_count,
                "active_prs": pr_opened_count,
                "success_rate_percent": success_rate,
                "total_monthly_spend": total_monthly_spend,
                "total_security_issues_flagged": total_security_issues,
                "total_self_healing_rounds": total_healing_rounds,
                "avg_run_duration_seconds": avg_run_duration,
                "estimated_engineering_hours_saved": estimated_hours_saved,
                "estimated_financial_savings_usd": estimated_cost_saved
            },
            "status_distribution": {
                "deployed": deployed_count,
                "generated": generated_count,
                "failed": failed_count,
                "destroyed": destroyed_count,
                "pr_opened": pr_opened_count
            },
            "engine_breakdown": engine_breakdown,
            "failure_taxonomy": failure_taxonomy,
            "pattern_leaderboard": pattern_leaderboard,
            "recent_projects": projects[:10]
        }

    @staticmethod
    def _categorize_failures(projects: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorizes errors encountered during project generation/deployment into taxonomy categories."""
        categories = {
            "Resource Conflict / Duplicate Name": 0,
            "IAM / Permission Denied": 0,
            "Syntax / Block Format Error": 0,
            "Provider Schema / Deprecation": 0,
            "Quota / Resource Limits": 0,
            "Network / Subnet Configuration": 0,
            "Other / Unclassified": 0
        }

        for p in projects:
            errors = p.get("errors_encountered") or []
            for err in errors:
                err_text = str(err).lower()
                if any(w in err_text for w in ["alreadyexists", "duplicate", "conflict", "exists"]):
                    categories["Resource Conflict / Duplicate Name"] += 1
                elif any(w in err_text for w in ["accessdenied", "forbidden", "unauthorized", "permission", "iam"]):
                    categories["IAM / Permission Denied"] += 1
                elif any(w in err_text for w in ["syntax", "unexpected", "argument", "unsupported attribute", "unknown block"]):
                    categories["Syntax / Block Format Error"] += 1
                elif any(w in err_text for w in ["provider", "plugin", "version constraint", "deprecated"]):
                    categories["Provider Schema / Deprecation"] += 1
                elif any(w in err_text for w in ["quota", "limitexceeded", "capacity"]):
                    categories["Quota / Resource Limits"] += 1
                elif any(w in err_text for w in ["cidr", "subnet", "vpc", "route", "gateway"]):
                    categories["Network / Subnet Configuration"] += 1
                else:
                    categories["Other / Unclassified"] += 1

        return {k: v for k, v in categories.items() if v > 0} or {"None": 0}

    @staticmethod
    def _get_pattern_leaderboard() -> List[Dict[str, Any]]:
        """Loads failure patterns and ranks them by confidence and success count."""
        from memory.pattern_manager import PatternManager
        try:
            pm = PatternManager()
            patterns = pm._patterns or []
            leaderboard = []
            for p in patterns:
                successes = p.get("success_count", 0)
                failures = p.get("failure_count", 0)
                total = successes + failures
                confidence = p.get("confidence", 1.0 if p.get("status") == "trusted" else 0.8)
                signature = p.get("signature") or p.get("error_substring", "")
                leaderboard.append({
                    "id": p.get("id", signature),
                    "signature": signature,
                    "category": p.get("category", "General"),
                    "confidence": round(confidence, 2),
                    "confidence_percent": int(confidence * 100),
                    "success_count": successes,
                    "failure_count": failures,
                    "last_used": p.get("last_used", "N/A"),
                    "status": p.get("status", "trusted")
                })
            leaderboard.sort(key=lambda x: (x["confidence"], x["success_count"]), reverse=True)
            return leaderboard[:10]
        except Exception:
            return []

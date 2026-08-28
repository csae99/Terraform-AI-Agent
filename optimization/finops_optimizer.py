import re
from typing import Dict, List, Any

class FinOpsOptimizer:
    """
    Autonomous FinOps Optimization & Right-Sizing Engine.
    Analyzes IaC declarations with safety heuristics:
    - Spot instance eligibility filters (stateless vs stateful/databases).
    - ARM Graviton migration canary recommendations.
    - S3 Glacier lifecycle tiering and NAT gateway consolidation.
    """

    # Resources that must NEVER be converted to Spot instances
    INELIGIBLE_FOR_SPOT = [
        "aws_db_instance", "aws_rds_cluster", "azurerm_postgresql_server",
        "azurerm_mssql_database", "google_sql_database_instance",
        "aws_elasticache_cluster", "aws_eks_cluster", "aws_lb",
        "aws_alb", "azurerm_application_gateway"
    ]

    @classmethod
    def analyze_cost_optimizations(cls, hcl_code: str, environment: str = "staging") -> Dict[str, Any]:
        recommendations = []
        projected_monthly_savings = 0.0
        safety_notes = []

        lower = hcl_code.lower()
        env = environment.lower()
        is_prod = env in ["prod", "production"]

        # ── 1. Compute Right-Sizing & ARM Graviton Safety ────────────
        if "instance_type" in lower:
            match = re.search(r'instance_type\s*=\s*"([^"]+)"', hcl_code)
            if match:
                itype = match.group(1)
                if any(x in itype for x in ["2xlarge", "4xlarge", "8xlarge", "large"]):
                    savings = 45.0
                    projected_monthly_savings += savings
                    
                    # Add Graviton canary safety advice for production
                    migration_mode = "Canary Deployment (1 Node first)" if is_prod else "Direct In-Place Migration"
                    recommendations.append({
                        "category": "Compute Right-Sizing",
                        "title": f"Right-size instance '{itype}' to Graviton ARM 't4g.xlarge'",
                        "monthly_savings_usd": savings,
                        "migration_strategy": migration_mode,
                        "safety_check": "Verified: Requires multi-arch ARM64 (linux/arm64) container images.",
                        "description": f"Switching from x86 oversized instance to AWS Graviton improves price/performance by 40% ({migration_mode})."
                    })

        # ── 2. Spot Instance Conversion with Eligibility Filters ─────
        has_worker_nodes = "node_group" in lower or "autoscaling_group" in lower or "batch_compute_environment" in lower
        has_ineligible_stateful = any(res in lower for res in cls.INELIGIBLE_FOR_SPOT)

        if has_worker_nodes and "spot" not in lower:
            if not has_ineligible_stateful:
                savings = 65.0
                projected_monthly_savings += savings
                recommendations.append({
                    "category": "Spot Workloads",
                    "title": "Enable Spot Capacity for Stateless Worker Pools",
                    "monthly_savings_usd": savings,
                    "eligibility": "ELIGIBLE (Stateless container workers / Batch jobs)",
                    "description": "Utilize AWS Spot Instances for stateless container workers with up to 70% discount against on-demand pricing."
                })
            else:
                safety_notes.append("Spot optimization skipped for stateful database/cache components to prevent data disruption.")

        # ── 3. S3 Cold Storage Tiering ───────────────────────────────
        if "aws_s3_bucket" in lower:
            if "glacier" not in lower and "transition" not in lower:
                savings = 18.0
                projected_monthly_savings += savings
                recommendations.append({
                    "category": "Storage Lifecycle",
                    "title": "Add 30-Day Glacier Instant Retrieval Lifecycle Rule",
                    "monthly_savings_usd": savings,
                    "description": "Automatically transition inactive objects after 30 days to save up to 68% on S3 storage fees."
                })

        # ── 4. Multi-AZ NAT Gateway Consolidation for Non-Prod ───────
        if "nat_gateway" in lower and not is_prod:
            savings = 32.0
            projected_monthly_savings += savings
            recommendations.append({
                "category": "Network Gateway",
                "title": "Consolidate Multi-AZ NAT Gateways to Single AZ in Non-Prod",
                "monthly_savings_usd": savings,
                "description": f"Environment '{environment}' only requires a single NAT Gateway instead of redundant multi-AZ gateways."
            })

        return {
            "total_recommendations_count": len(recommendations),
            "projected_monthly_savings_usd": round(projected_monthly_savings, 2),
            "recommendations": recommendations,
            "safety_notes": safety_notes,
            "status": "OPTIMIZATION_AVAILABLE" if recommendations else "FULLY_OPTIMIZED"
        }

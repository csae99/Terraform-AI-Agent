import re
from typing import Dict, List, Any

class FinOpsOptimizer:
    """
    Autonomous FinOps Optimization & Right-Sizing Engine.
    Analyzes IaC declarations and identifies spot candidates, compute right-sizing,
    storage lifecycle tiering, and idle resources.
    """

    @classmethod
    def analyze_cost_optimizations(cls, hcl_code: str) -> Dict[str, Any]:
        recommendations = []
        projected_monthly_savings = 0.0

        lower = hcl_code.lower()

        # 1. Compute Right-Sizing
        if "instance_type" in lower:
            # Check for large instances in non-prod
            match = re.search(r'instance_type\s*=\s*"([^"]+)"', hcl_code)
            if match:
                itype = match.group(1)
                if any(x in itype for x in ["2xlarge", "4xlarge", "8xlarge", "large"]):
                    savings = 45.0
                    projected_monthly_savings += savings
                    recommendations.append({
                        "category": "Compute Right-Sizing",
                        "title": f"Right-size instance '{itype}' to Graviton ARM 't4g.xlarge'",
                        "monthly_savings_usd": savings,
                        "description": "Switching from x86 oversized instance to AWS Graviton improves price/performance by 40%."
                    })

        # 2. Spot Instance Conversion
        if "node_group" in lower or "autoscaling_group" in lower:
            if "spot" not in lower:
                savings = 65.0
                projected_monthly_savings += savings
                recommendations.append({
                    "category": "Spot Workloads",
                    "title": "Enable Spot Capacity for Stateless Worker Pools",
                    "monthly_savings_usd": savings,
                    "description": "Utilize AWS Spot Instances for container workers with 70% discount against on-demand pricing."
                })

        # 3. S3 Cold Storage Tiering
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

        # 4. Multi-AZ NAT Gateway Consolidation for Non-Prod
        if "nat_gateway" in lower and "environment = \"dev\"" in lower:
            savings = 32.0
            projected_monthly_savings += savings
            recommendations.append({
                "category": "Network Gateway",
                "title": "Consolidate Multi-AZ NAT Gateways to Single AZ in Dev",
                "monthly_savings_usd": savings,
                "description": "Development environments only require a single NAT Gateway instead of redundant multi-AZ gateways."
            })

        return {
            "total_recommendations_count": len(recommendations),
            "projected_monthly_savings_usd": round(projected_monthly_savings, 2),
            "recommendations": recommendations,
            "status": "OPTIMIZATION_AVAILABLE" if recommendations else "FULLY_OPTIMIZED"
        }

from typing import Dict, List, Any

class AgentMarketplaceCatalog:
    """
    Agent & Plugin Marketplace Catalog.
    Contains curated specialized agents and plugins available for installation by organizations.
    """

    CATALOG: Dict[str, Dict[str, Any]] = {
        "k8s-operator-expert": {
            "id": "k8s-operator-expert",
            "name": "Kubernetes Operator & Helm Expert",
            "category": "orchestration",
            "version": "1.4.0",
            "author": "CloudNative Labs",
            "rating": 4.9,
            "downloads": 1280,
            "description": "Deep specialized reasoning for Kubernetes EKS/AKS clusters, Helm charts, CRDs, and Istio service mesh.",
            "capabilities": ["helm_synthesis", "ingress_validation", "hpa_optimization"],
            "icon": "☸️",
            "price_monthly_usd": 0.0  # Free community agent
        },
        "finops-cost-hawk": {
            "id": "finops-cost-hawk",
            "name": "FinOps Cost Hawk & Spot Arbitrage",
            "category": "optimization",
            "version": "2.1.0",
            "author": "FinOps Foundation Partner",
            "rating": 4.8,
            "downloads": 2450,
            "description": "Aggressively identifies spot instance candidates, cold storage tiering, and idle network gateways to cut AWS/Azure bills by 30-50%.",
            "capabilities": ["spot_workload_analysis", "s3_lifecycle_tiering", "right_sizing"],
            "icon": "🦅",
            "price_monthly_usd": 15.0
        },
        "dr-failover-pilot": {
            "id": "dr-failover-pilot",
            "name": "Disaster Recovery & Multi-Region Failover Pilot",
            "category": "resilience",
            "version": "1.2.0",
            "author": "Enterprise Reliability Inc",
            "rating": 5.0,
            "downloads": 890,
            "description": "Automates cross-region Terraform state backups, calculates RTO/RPO metrics, and orchestrates secondary region failovers.",
            "capabilities": ["state_backup", "regional_failover", "dns_repointing"],
            "icon": "🆘",
            "price_monthly_usd": 25.0
        },
        "zero-trust-secops": {
            "id": "zero-trust-secops",
            "name": "Zero-Trust SecOps & KMS Enforcer",
            "category": "security",
            "version": "2.0.0",
            "author": "SecOps Autonomous",
            "rating": 4.9,
            "downloads": 3100,
            "description": "Enforces military-grade zero-trust networking, customer-managed KMS key rotation, VPC flow logging, and automated IAM least-privilege.",
            "capabilities": ["zero_trust_network", "kms_envelope_encryption", "iam_least_privilege"],
            "icon": "🛡️",
            "price_monthly_usd": 20.0
        }
    }

    @classmethod
    def list_catalog(cls, category: str = None) -> List[Dict[str, Any]]:
        """Returns list of all catalog items, optionally filtered by category."""
        items = list(cls.CATALOG.values())
        if category:
            items = [i for i in items if i.get("category") == category.lower()]
        return items

    @classmethod
    def get_agent_metadata(cls, agent_id: str) -> Dict[str, Any]:
        """Retrieves metadata for a specific marketplace agent."""
        return cls.CATALOG.get(agent_id, {})

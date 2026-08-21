from typing import Dict, Any

class ProviderComparator:
    """
    Multi-Cloud Service Mapping & Pricing Comparator.
    Equivalence matrix comparing AWS, Azure, and GCP enterprise cloud services.
    """

    SERVICE_EQUIVALENCY = {
        "kubernetes": {
            "AWS": {"service": "EKS", "base_price_monthly": 73.0, "ha_sla": "99.95%"},
            "Azure": {"service": "AKS", "base_price_monthly": 0.0, "ha_sla": "99.95%"},
            "GCP": {"service": "GKE Standard", "base_price_monthly": 73.0, "ha_sla": "99.95%"}
        },
        "postgresql": {
            "AWS": {"service": "RDS PostgreSQL (db.t3.medium)", "base_price_monthly": 49.0, "ha_sla": "99.95%"},
            "Azure": {"service": "Azure Database for PostgreSQL (Flexible)", "base_price_monthly": 43.0, "ha_sla": "99.99%"},
            "GCP": {"service": "Cloud SQL PostgreSQL (db-custom-2-7680)", "base_price_monthly": 51.0, "ha_sla": "99.95%"}
        },
        "object_storage": {
            "AWS": {"service": "S3 Standard ($0.023/GB)", "base_price_monthly": 2.30, "ha_sla": "99.99%"},
            "Azure": {"service": "Blob Storage Hot ($0.018/GB)", "base_price_monthly": 1.80, "ha_sla": "99.99%"},
            "GCP": {"service": "Cloud Storage Standard ($0.020/GB)", "base_price_monthly": 2.00, "ha_sla": "99.95%"}
        },
        "serverless": {
            "AWS": {"service": "AWS Lambda + API Gateway", "base_price_monthly": 5.0, "ha_sla": "99.95%"},
            "Azure": {"service": "Azure Functions + API Management", "base_price_monthly": 4.5, "ha_sla": "99.95%"},
            "GCP": {"service": "Cloud Run + Cloud Endpoints", "base_price_monthly": 4.0, "ha_sla": "99.95%"}
        }
    }

    @classmethod
    def get_service_mapping(cls, category: str) -> Dict[str, Any]:
        return cls.SERVICE_EQUIVALENCY.get(category.lower(), {})

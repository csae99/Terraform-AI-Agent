from typing import Dict, List, Any

class ServiceCatalogTemplates:
    """
    Golden Path Service Catalog for Internal Developer Portal.
    Pre-architected, compliant, and cost-optimized infrastructure blueprints.
    """

    TEMPLATES: Dict[str, Dict[str, Any]] = {
        "microservices-k8s-stack": {
            "id": "microservices-k8s-stack",
            "name": "Production Microservices Kubernetes Stack",
            "category": "containers",
            "provider": "AWS",
            "estimated_cost_monthly": 125.0,
            "compliance": ["SOC2", "CIS"],
            "description": "Multi-AZ EKS cluster with managed node groups, ALB Ingress Controller, and Prometheus observability.",
            "hcl_template": """# Golden Path: Production Microservices K8s Stack
module "vpc" {
  source = "./modules/vpc"
  multi_az = true
  enable_nat_gateway = true
}
module "eks" {
  source = "./modules/eks"
  cluster_name = "prod-microservices"
  node_count = 3
}
"""
        },
        "serverless-event-stream": {
            "id": "serverless-event-stream",
            "name": "Serverless Event Stream & API",
            "category": "serverless",
            "provider": "AWS",
            "estimated_cost_monthly": 15.0,
            "compliance": ["SOC2", "PCI-DSS"],
            "description": "API Gateway + Lambda + SQS Dead-Letter Queue + DynamoDB with on-demand scaling.",
            "hcl_template": """# Golden Path: Serverless Event Stream
module "api_gateway" {
  source = "./modules/api_gateway"
}
module "event_processing" {
  source = "./modules/lambda"
  sqs_dlq_enabled = true
}
"""
        },
        "secure-ml-vault": {
            "id": "secure-ml-vault",
            "name": "Secure Machine Learning Data Vault",
            "category": "ai_ml",
            "provider": "AWS",
            "estimated_cost_monthly": 85.0,
            "compliance": ["HIPAA", "SOC2"],
            "description": "KMS-encrypted S3 data lake, private VPC endpoints, IAM least-privilege, and CloudTrail auditing.",
            "hcl_template": """# Golden Path: Secure ML Data Vault
module "s3_data_vault" {
  source = "./modules/s3"
  kms_master_key_id = "arn:aws:kms:us-east-1:123456789012:key/ml-vault"
  block_public_acls = true
  versioning = true
}
"""
        }
    }

    @classmethod
    def list_templates(cls) -> List[Dict[str, Any]]:
        return list(cls.TEMPLATES.values())

    @classmethod
    def get_template(cls, template_id: str) -> Dict[str, Any]:
        return cls.TEMPLATES.get(template_id, {})

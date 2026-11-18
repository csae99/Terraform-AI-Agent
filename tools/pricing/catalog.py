import os
import sqlite3
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "terraform_agent.db")

class PricingCatalogManager:
    """Manages the database-backed cloud pricing catalog for instant, reliable estimation."""

    @staticmethod
    def get_connection():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def init_db():
        """Ensure pricing_catalog table exists and is seeded with comprehensive cloud rates."""
        conn = PricingCatalogManager.get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pricing_catalog (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        provider TEXT NOT NULL,
                        service TEXT NOT NULL,
                        sku TEXT NOT NULL,
                        display_name TEXT NOT NULL,
                        vcpus INTEGER DEFAULT 0,
                        memory_gb REAL DEFAULT 0.0,
                        hourly_usd REAL NOT NULL,
                        monthly_usd REAL NOT NULL,
                        region TEXT DEFAULT 'us-east-1',
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(provider, service, sku, region)
                    );
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pricing_sku ON pricing_catalog(sku);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pricing_provider_service ON pricing_catalog(provider, service);")

                count = conn.execute("SELECT COUNT(*) FROM pricing_catalog;").fetchone()[0]
                if count == 0:
                    PricingCatalogManager._seed_catalog(conn)
        finally:
            conn.close()

    @staticmethod
    def _seed_catalog(conn):
        """Seed initial real-world pricing entries for AWS, Azure, GCP and Managed Services."""
        catalog_entries = [
            # ── AWS EC2 Compute ──
            ("aws", "ec2", "t3.nano", "AWS t3.nano (2 vCPU, 0.5 GB)", 2, 0.5, 0.0052, 3.80, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.micro", "AWS t3.micro (2 vCPU, 1 GB)", 2, 1.0, 0.0104, 7.60, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.small", "AWS t3.small (2 vCPU, 2 GB)", 2, 2.0, 0.0208, 15.20, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.medium", "AWS t3.medium (2 vCPU, 4 GB)", 2, 4.0, 0.0416, 30.40, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.large", "AWS t3.large (2 vCPU, 8 GB)", 2, 8.0, 0.0832, 60.74, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.xlarge", "AWS t3.xlarge (4 vCPU, 16 GB)", 4, 16.0, 0.1664, 121.47, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "t3.2xlarge", "AWS t3.2xlarge (8 vCPU, 32 GB)", 8, 32.0, 0.3328, 242.94, "us-east-1", "Burstable General Purpose"),
            ("aws", "ec2", "c6.large", "AWS c6.large (2 vCPU, 4 GB)", 2, 4.0, 0.0850, 62.05, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6i.large", "AWS c6i.large (2 vCPU, 4 GB)", 2, 4.0, 0.0850, 62.05, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6.xlarge", "AWS c6.xlarge (4 vCPU, 8 GB)", 4, 8.0, 0.1700, 124.10, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6i.xlarge", "AWS c6i.xlarge (4 vCPU, 8 GB)", 4, 8.0, 0.1700, 124.10, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6.2xlarge", "AWS c6.2xlarge (8 vCPU, 16 GB)", 8, 16.0, 0.3400, 248.20, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6i.2xlarge", "AWS c6i.2xlarge (8 vCPU, 16 GB)", 8, 16.0, 0.3400, 248.20, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6.4xlarge", "AWS c6.4xlarge (16 vCPU, 32 GB)", 16, 32.0, 0.6800, 496.40, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6i.4xlarge", "AWS c6i.4xlarge (16 vCPU, 32 GB)", 16, 32.0, 0.6800, 496.40, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "c6.8xlarge", "AWS c6.8xlarge (32 vCPU, 64 GB)", 32, 64.0, 1.3600, 992.80, "us-east-1", "Compute Optimized"),
            ("aws", "ec2", "m5.large", "AWS m5.large (2 vCPU, 8 GB)", 2, 8.0, 0.0960, 70.08, "us-east-1", "General Purpose"),
            ("aws", "ec2", "m5.xlarge", "AWS m5.xlarge (4 vCPU, 16 GB)", 4, 16.0, 0.1920, 140.16, "us-east-1", "General Purpose"),
            ("aws", "ec2", "m5.2xlarge", "AWS m5.2xlarge (8 vCPU, 32 GB)", 8, 32.0, 0.3840, 280.32, "us-east-1", "General Purpose"),
            ("aws", "ec2", "m5.4xlarge", "AWS m5.4xlarge (16 vCPU, 64 GB)", 16, 64.0, 0.7680, 560.64, "us-east-1", "General Purpose"),
            ("aws", "ec2", "r5.large", "AWS r5.large (2 vCPU, 16 GB)", 2, 16.0, 0.1260, 91.98, "us-east-1", "Memory Optimized"),
            ("aws", "ec2", "r5.xlarge", "AWS r5.xlarge (4 vCPU, 32 GB)", 4, 32.0, 0.2520, 183.96, "us-east-1", "Memory Optimized"),
            ("aws", "ec2", "r5.2xlarge", "AWS r5.2xlarge (8 vCPU, 64 GB)", 8, 64.0, 0.5040, 367.92, "us-east-1", "Memory Optimized"),
            ("aws", "ec2", "g4dn.xlarge", "AWS g4dn.xlarge (4 vCPU, 16 GB, 1 GPU)", 4, 16.0, 0.5260, 383.98, "us-east-1", "GPU Accelerated"),
            ("aws", "ec2", "p3.2xlarge", "AWS p3.2xlarge (8 vCPU, 61 GB, 1 V100 GPU)", 8, 61.0, 3.0600, 2233.80, "us-east-1", "Deep Learning GPU"),

            # ── Azure Virtual Machines ──
            ("azure", "vm", "Standard_B1s", "Azure Standard_B1s (1 vCPU, 1 GB)", 1, 1.0, 0.0104, 7.59, "eastus", "Burstable VM"),
            ("azure", "vm", "Standard_B2s", "Azure Standard_B2s (2 vCPU, 4 GB)", 2, 4.0, 0.0416, 30.37, "eastus", "Burstable VM"),
            ("azure", "vm", "Standard_B4ms", "Azure Standard_B4ms (4 vCPU, 16 GB)", 4, 16.0, 0.1660, 121.18, "eastus", "Burstable VM"),
            ("azure", "vm", "Standard_D2s_v5", "Azure Standard_D2s_v5 (2 vCPU, 8 GB)", 2, 8.0, 0.0960, 70.08, "eastus", "General Purpose"),
            ("azure", "vm", "Standard_D4s_v5", "Azure Standard_D4s_v5 (4 vCPU, 16 GB)", 4, 16.0, 0.1920, 140.16, "eastus", "General Purpose"),
            ("azure", "vm", "Standard_D8s_v5", "Azure Standard_D8s_v5 (8 vCPU, 32 GB)", 8, 32.0, 0.3840, 280.32, "eastus", "General Purpose"),
            ("azure", "vm", "Standard_E4s_v5", "Azure Standard_E4s_v5 (4 vCPU, 32 GB)", 4, 32.0, 0.2520, 183.96, "eastus", "Memory Optimized"),

            # ── GCP Compute Engine ──
            ("gcp", "compute", "e2-micro", "GCP e2-micro (2 vCPU, 1 GB)", 2, 1.0, 0.0084, 6.13, "us-central1", "Cost Optimized VM"),
            ("gcp", "compute", "e2-small", "GCP e2-small (2 vCPU, 2 GB)", 2, 2.0, 0.0168, 12.26, "us-central1", "Cost Optimized VM"),
            ("gcp", "compute", "e2-medium", "GCP e2-medium (2 vCPU, 4 GB)", 2, 4.0, 0.0336, 24.53, "us-central1", "Cost Optimized VM"),
            ("gcp", "compute", "e2-standard-2", "GCP e2-standard-2 (2 vCPU, 8 GB)", 2, 8.0, 0.0670, 48.91, "us-central1", "Standard VM"),
            ("gcp", "compute", "e2-standard-4", "GCP e2-standard-4 (4 vCPU, 16 GB)", 4, 16.0, 0.1340, 97.82, "us-central1", "Standard VM"),
            ("gcp", "compute", "n2-standard-4", "GCP n2-standard-4 (4 vCPU, 16 GB)", 4, 16.0, 0.1940, 141.62, "us-central1", "Balanced Performance"),
            ("gcp", "compute", "n2-standard-8", "GCP n2-standard-8 (8 vCPU, 32 GB)", 8, 32.0, 0.3880, 283.24, "us-central1", "Balanced Performance"),

            # ── AWS RDS Databases ──
            ("aws", "rds", "db.t3.micro", "RDS db.t3.micro (2 vCPU, 1 GB)", 2, 1.0, 0.0170, 12.41, "us-east-1", "Single-AZ Database Instance"),
            ("aws", "rds", "db.t3.small", "RDS db.t3.small (2 vCPU, 2 GB)", 2, 2.0, 0.0340, 24.82, "us-east-1", "Single-AZ Database Instance"),
            ("aws", "rds", "db.t3.medium", "RDS db.t3.medium (2 vCPU, 4 GB)", 2, 4.0, 0.0680, 49.64, "us-east-1", "Single-AZ Database Instance"),
            ("aws", "rds", "db.t3.large", "RDS db.t3.large (2 vCPU, 8 GB)", 2, 8.0, 0.1360, 99.28, "us-east-1", "Single-AZ Database Instance"),
            ("aws", "rds", "db.m5.large", "RDS db.m5.large (2 vCPU, 8 GB)", 2, 8.0, 0.1820, 132.86, "us-east-1", "General Purpose DB Instance"),
            ("aws", "rds", "db.m5.xlarge", "RDS db.m5.xlarge (4 vCPU, 16 GB)", 4, 16.0, 0.3640, 265.72, "us-east-1", "General Purpose DB Instance"),
            ("aws", "rds", "db.r5.large", "RDS db.r5.large (2 vCPU, 16 GB)", 2, 16.0, 0.2400, 175.20, "us-east-1", "Memory Optimized DB Instance"),
            ("aws", "rds", "db.r5.2xlarge", "RDS db.r5.2xlarge (8 vCPU, 64 GB)", 8, 64.0, 0.9600, 700.80, "us-east-1", "Memory Optimized DB Instance"),

            # ── Managed Platform Services ──
            ("aws", "managed", "eks_control_plane", "AWS EKS Managed Control Plane", 0, 0.0, 0.1000, 73.00, "us-east-1", "Managed Kubernetes Master"),
            ("azure", "managed", "aks_control_plane", "Azure AKS Managed Control Plane", 0, 0.0, 0.1000, 73.00, "eastus", "Managed AKS Control Plane"),
            ("gcp", "managed", "gke_control_plane", "GCP GKE Managed Control Plane", 0, 0.0, 0.1000, 73.00, "us-central1", "Managed GKE Cluster Fee"),
            ("aws", "managed", "nat_gateway", "AWS VPC NAT Gateway", 0, 0.0, 0.0450, 32.85, "us-east-1", "Outbound Internet Gateway"),
            ("aws", "managed", "alb", "Application Load Balancer", 0, 0.0, 0.0300, 21.90, "us-east-1", "L7 HTTP/HTTPS Load Balancer"),
            ("aws", "managed", "nlb", "Network Load Balancer", 0, 0.0, 0.0250, 18.25, "us-east-1", "L4 Ultra-low latency Load Balancer"),
            ("aws", "managed", "dynamodb", "Amazon DynamoDB Table", 0, 0.0, 0.0070, 5.00, "us-east-1", "NoSQL Serverless On-Demand Table"),
            ("aws", "managed", "lambda", "AWS Lambda Serverless Microservice", 0, 0.0, 0.0070, 5.00, "us-east-1", "Serverless Compute & API Gateway"),
            ("gcp", "managed", "cloudrun", "Google Cloud Run Service", 0, 0.0, 0.0110, 8.00, "us-central1", "Serverless Container Instance"),

            # ── Storage Unit Baselines (Per GB / Standard allocation) ──
            ("aws", "storage", "ebs_gp3_100gb", "100 GB EBS gp3 SSD Volume", 0, 0.0, 0.0110, 8.00, "us-east-1", "$0.08 per GB-month"),
            ("aws", "storage", "s3_standard_100gb", "100 GB S3 Standard Storage", 0, 0.0, 0.0032, 2.30, "us-east-1", "$0.023 per GB-month"),
            ("aws", "storage", "s3_glacier_100gb", "100 GB S3 Glacier Vault", 0, 0.0, 0.0014, 1.00, "us-east-1", "$0.004 per GB-month")
        ]

        conn.executemany("""
            INSERT OR IGNORE INTO pricing_catalog 
            (provider, service, sku, display_name, vcpus, memory_gb, hourly_usd, monthly_usd, region, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, catalog_entries)
        logger.info(f"Seeded {len(catalog_entries)} entries into pricing_catalog table.")

    @staticmethod
    def get_catalog(provider: Optional[str] = None, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve catalog items, optionally filtered by provider and service."""
        PricingCatalogManager.init_db()
        conn = PricingCatalogManager.get_connection()
        try:
            query = "SELECT id, provider, service, sku, display_name, vcpus, memory_gb, hourly_usd, monthly_usd, region, description FROM pricing_catalog WHERE 1=1"
            params = []
            if provider:
                query += " AND provider = ?"
                params.append(provider.lower())
            if service:
                query += " AND service = ?"
                params.append(service.lower())
            query += " ORDER BY provider, service, monthly_usd ASC"
            
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def lookup_sku(sku: str, provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Look up exact SKU pricing from database."""
        PricingCatalogManager.init_db()
        conn = PricingCatalogManager.get_connection()
        try:
            query = "SELECT * FROM pricing_catalog WHERE sku = ?"
            params = [sku.lower()]
            if provider:
                query += " AND provider = ?"
                params.append(provider.lower())
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


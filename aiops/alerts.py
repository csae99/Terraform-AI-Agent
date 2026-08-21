from typing import List, Dict, Any
from datetime import datetime
from tools.project.tracker import SessionLocal, ProjectModel

class AIOpsAlertManager:
    """
    Real-Time AIOps Incident & Governance Alert System.
    Monitors budget breach thresholds, consecutive failures, and unhealed drift.
    """

    @classmethod
    def get_active_alerts(cls, org_id: int = None) -> List[Dict[str, Any]]:
        alerts = []
        session = SessionLocal()
        try:
            q = session.query(ProjectModel)
            if org_id:
                q = q.filter(ProjectModel.org_id == org_id)
            projects = q.all()

            for p in projects:
                # 1. Budget Anomaly Alert
                if p.estimated_cost and p.budget and p.estimated_cost > p.budget:
                    alerts.append({
                        "id": f"alert-budget-{p.slug}",
                        "severity": "HIGH",
                        "type": "BudgetExceeded",
                        "title": f"Workspace '{p.slug}' Over Budget",
                        "description": f"Estimated cloud spend (${p.estimated_cost}/mo) exceeds budget threshold of ${p.budget}/mo.",
                        "resource_slug": p.slug,
                        "timestamp": p.updated_at.isoformat() + "Z" if p.updated_at else datetime.utcnow().isoformat() + "Z"
                    })

                # 2. Security Drift Alert
                if p.drift_status == "drifted":
                    alerts.append({
                        "id": f"alert-drift-{p.slug}",
                        "severity": "CRITICAL",
                        "type": "InfrastructureDrift",
                        "title": f"Cloud Drift Detected in '{p.slug}'",
                        "description": "Live cloud resources have diverged from the Terraform state definition.",
                        "resource_slug": p.slug,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    })

                # 3. High Failure Rounds Alert
                if (p.healing_rounds_taken or 1) >= 3 and p.status == "failed":
                    alerts.append({
                        "id": f"alert-failure-{p.slug}",
                        "severity": "MEDIUM",
                        "type": "SelfHealingExhaustion",
                        "title": f"Self-Healing Max Retries Reached in '{p.slug}'",
                        "description": "Agent attempted 3 self-healing remediation rounds without successful syntax resolution.",
                        "resource_slug": p.slug,
                        "timestamp": p.updated_at.isoformat() + "Z" if p.updated_at else datetime.utcnow().isoformat() + "Z"
                    })

            return alerts
        finally:
            session.close()

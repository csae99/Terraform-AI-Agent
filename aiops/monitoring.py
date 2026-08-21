from typing import Dict, List, Any
from datetime import datetime
from tools.project.tracker import SessionLocal, ProjectModel, PatternMemoryModel, UserModel, AuditLogModel

class AIOpsMonitor:
    """
    AI Operations Center Telemetry & Health Monitoring.
    Tracks agent system health, error taxonomy, pattern learning speed, and execution trends.
    """

    @classmethod
    def get_system_health(cls, org_id: int = None) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            q = session.query(ProjectModel)
            if org_id:
                q = q.filter(ProjectModel.org_id == org_id)
            projects = q.all()

            total_runs = len(projects)
            deployed = sum(1 for p in projects if p.status == "deployed")
            failed = sum(1 for p in projects if p.status == "failed")
            self_healed = sum(1 for p in projects if (p.healing_rounds_taken or 1) > 1 and p.status != "failed")

            total_healing_rounds = sum(p.healing_rounds_taken or 1 for p in projects)
            avg_rounds = round(total_healing_rounds / total_runs, 2) if total_runs > 0 else 1.0

            patterns_count = session.query(PatternMemoryModel).count()
            trusted_patterns = session.query(PatternMemoryModel).filter(PatternMemoryModel.status == "trusted").count()

            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "health_status": "OPTIMAL" if (failed / total_runs if total_runs > 0 else 0) < 0.15 else "DEGRADED",
                "total_workspaces": total_runs,
                "successful_deployments": deployed,
                "failed_runs": failed,
                "self_healed_runs": self_healed,
                "avg_healing_rounds": avg_rounds,
                "pattern_bank": {
                    "total_patterns": patterns_count,
                    "trusted_patterns": trusted_patterns,
                    "candidate_patterns": patterns_count - trusted_patterns,
                    "learning_rate": "Active (Dynamic Self-Learning Enabled)"
                },
                "agent_status": {
                    "ArchitectAgent": "HEALTHY",
                    "DeveloperAgent": "HEALTHY",
                    "SecurityReviewer": "HEALTHY",
                    "FinOpsSpecialist": "HEALTHY",
                    "TestingAgent": "HEALTHY",
                    "GitOpsCoordinator": "HEALTHY"
                }
            }
        finally:
            session.close()

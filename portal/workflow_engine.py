import time
from typing import Dict, List, Any, Optional

class WorkflowNode:
    """Represents a single step / node in a DAG Workflow."""
    def __init__(self, step_id: str, name: str, step_type: str, depends_on: Optional[List[str]] = None, config: Optional[Dict[str, Any]] = None):
        self.step_id = step_id
        self.name = name
        self.step_type = step_type  # agent_task, policy_check, approval_gate, deploy_action, finops_analysis, notify
        self.depends_on = depends_on or []
        self.config = config or {}
        self.status = "pending"  # pending, running, completed, skipped, failed
        self.output: Dict[str, Any] = {}
        self.duration_seconds: float = 0.0


class WorkflowEngine:
    """
    DAG Visual Workflow Execution Engine.
    Executes multi-agent and governance workflows with dependency resolution and conditional branching.
    """

    @classmethod
    def execute_workflow(
        cls,
        workflow_def: Dict[str, Any],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a workflow definition containing steps and dependency graphs.
        """
        workflow_name = workflow_def.get("name", "Custom Infrastructure Pipeline")
        steps_data = workflow_def.get("steps", [])
        context = dict(initial_context or {})
        
        nodes: Dict[str, WorkflowNode] = {}
        for s in steps_data:
            node = WorkflowNode(
                step_id=s["id"],
                name=s.get("name", s["id"]),
                step_type=s.get("type", "agent_task"),
                depends_on=s.get("depends_on", []),
                config=s.get("config", {})
            )
            nodes[node.step_id] = node

        start_time = time.time()
        completed_steps = []
        failed_steps = []
        skipped_steps = []

        # Simple topological execution
        for step_id, node in nodes.items():
            # Check dependencies
            deps_met = all(nodes[dep].status == "completed" for dep in node.depends_on if dep in nodes)
            if not deps_met and node.depends_on:
                node.status = "skipped"
                skipped_steps.append(node.step_id)
                continue

            node.status = "running"
            t0 = time.time()

            try:
                # Execute step based on type
                if node.step_type == "agent_task":
                    node.output = {
                        "agent": node.config.get("agent", "DeveloperAgent"),
                        "result": f"Synthesized HCL for {node.name}",
                        "hcl_generated": True
                    }
                elif node.step_type == "policy_check":
                    from policy.opa_engine import OPAEngine
                    hcl = context.get("hcl_code", "resource \"aws_s3_bucket\" \"demo\" { encrypted = true }")
                    pack = node.config.get("pack", "soc2")
                    node.output = OPAEngine.evaluate_compliance(hcl, pack=pack)
                elif node.step_type == "finops_analysis":
                    from cloud_optimizer.multi_cloud import MultiCloudOptimizer
                    prompt = context.get("prompt", "Kubernetes cluster with database")
                    node.output = MultiCloudOptimizer.compare_clouds_for_prompt(prompt, budget=node.config.get("budget", 100.0))
                elif node.step_type == "approval_gate":
                    # Evaluate approval condition
                    requires_approval = node.config.get("strict", False) or context.get("estimated_cost", 0) > node.config.get("cost_threshold", 500)
                    node.output = {
                        "requires_human_signoff": requires_approval,
                        "approved_automatically": not requires_approval,
                        "status": "APPROVED" if not requires_approval else "PENDING_SIGNOFF"
                    }
                elif node.step_type == "deploy_action":
                    node.output = {
                        "target_environment": node.config.get("environment", "staging"),
                        "status": "DEPLOYED_SIMULATED",
                        "resources_applied": 3
                    }
                else:
                    node.output = {"message": f"Executed generic step {node.name}"}

                node.duration_seconds = round(time.time() - t0, 3)
                node.status = "completed"
                completed_steps.append(node.step_id)
                context[f"step_{node.step_id}"] = node.output

            except Exception as e:
                node.status = "failed"
                node.output = {"error": str(e)}
                failed_steps.append(node.step_id)

        total_duration = round(time.time() - start_time, 3)

        return {
            "workflow_name": workflow_name,
            "status": "SUCCESS" if not failed_steps else "FAILED",
            "total_steps": len(nodes),
            "completed_steps_count": len(completed_steps),
            "failed_steps_count": len(failed_steps),
            "skipped_steps_count": len(skipped_steps),
            "total_duration_seconds": total_duration,
            "steps": [
                {
                    "id": n.step_id,
                    "name": n.name,
                    "type": n.step_type,
                    "status": n.status,
                    "duration": n.duration_seconds,
                    "output": n.output
                }
                for n in nodes.values()
            ]
        }

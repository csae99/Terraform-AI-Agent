import os
import subprocess
from typing import Optional
from crewai.tools import tool
from tools.engine import EngineFactory

class DeploymentTools:
    
    @staticmethod
    def _save_log(project_path, log_name, content):
        """Saves tool output to a log file for persistent audit."""
        try:
            log_dir = os.path.join(project_path, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, f"{log_name}.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(content)
            return f" (Log saved: logs/{log_name}.log)"
        except Exception:
            return " (Warning: Failed to save log)"

    @tool("Run Terraform Plan")
    def run_terraform_plan(project_slug: str, is_destroy: bool = False, engine_name: Optional[str] = None) -> str:
        """
        Executes 'plan' for a specific project using the active IaC engine (Terraform/OpenTofu).
        If is_destroy=True, it generates a destruction plan.
        Returns the plan output or detailed error messages.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        engine = EngineFactory.get_engine(engine_name)
        result = engine.plan(project_path, is_destroy=is_destroy)
        
        log_name = f"{engine.name}_plan_destroy" if is_destroy else f"{engine.name}_plan"
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, log_name, combined_output)

        if result["success"]:
            return f"✅ {engine.name.capitalize()} Plan Succeeded{log_msg}:\n{result['stdout']}"
        else:
            return f"❌ {engine.name.capitalize()} Plan Failed{log_msg}:\n{result['stderr']}"

    @tool("Run Terraform Apply")
    def run_terraform_apply(project_slug: str, engine_name: Optional[str] = None) -> str:
        """
        Executes 'apply -auto-approve' for a specific project using the active IaC engine (Terraform/OpenTofu).
        WARNING: This creates real cloud resources and may incur costs.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        engine = EngineFactory.get_engine(engine_name)
        result = engine.apply(project_path, auto_approve=True)
        
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, f"{engine.name}_apply", combined_output)

        if result["success"]:
            return f"🚀 Deployment Successful!{log_msg}\nOutputs:\n{result['stdout']}"
        else:
            return f"❌ Deployment Failed with API Error{log_msg}:\n{result['stderr']}\n\nSTDOUT Trace:\n{result['stdout']}"

    @tool("Run Terraform Destroy")
    def run_terraform_destroy(project_slug: str, engine_name: Optional[str] = None) -> str:
        """
        Executes 'destroy -auto-approve' to clean up infrastructure using the active IaC engine.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        engine = EngineFactory.get_engine(engine_name)
        result = engine.destroy(project_path, auto_approve=True)
        
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, f"{engine.name}_destroy", combined_output)

        if result["success"]:
            return f"🧹 Infrastructure successfully destroyed.{log_msg}"
        else:
            return f"❌ Destroy Failed{log_msg}:\n{result['stderr']}"

    @tool("Detect Infrastructure Drift")
    def detect_drift(project_slug: str, engine_name: Optional[str] = None) -> str:
        """
        Detects if the actual cloud state has drifted from the IaC code.
        Uses 'plan -detailed-exitcode'.
        Exit codes: 0=In Sync, 2=Drift Detected, 1=Error.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        engine = EngineFactory.get_engine(engine_name)
        result = engine.plan(project_path, detailed_exitcode=True)
        
        exit_code = result["exit_code"]
        stdout = result["stdout"]
        
        if exit_code == 0:
            return f"✅ IN SYNC: The actual infrastructure matches the {engine.name.capitalize()} configuration exactly."
        elif exit_code == 2:
            summary = "Drift detected."
            for line in stdout.splitlines():
                if "Plan:" in line:
                    summary = line
                    break
            return f"⚠️ DRIFT DETECTED: {summary}\n\nDetailed Plan:\n{stdout}"
        else:
            return f"❌ ERROR during drift check:\n{result['stderr']}"



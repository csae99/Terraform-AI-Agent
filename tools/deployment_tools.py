import os
import subprocess
from crewai.tools import tool

class DeploymentTools:
    
    @staticmethod
    def _run_command(command, cwd):
        """Helper to run shell commands and capture output."""
        try:
            process = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                shell=True
            )
            return {
                "success": process.returncode == 0,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode
            }
        except Exception as e:
            return {"success": False, "stderr": str(e), "exit_code": -1}

    @tool("Run Terraform Plan")
    def run_terraform_plan(project_slug: str) -> str:
        """
        Executes 'terraform plan' for a specific project.
        Returns the plan output or detailed error messages.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        # Ensure init is run first
        DeploymentTools._run_command("terraform init -backend=false", project_path)
        
        result = DeploymentTools._run_command("terraform plan -no-color", project_path)
        if result["success"]:
            return f"✅ Terraform Plan Succeeded:\n{result['stdout']}"
        else:
            return f"❌ Terraform Plan Failed:\n{result['stderr']}"

    @tool("Run Terraform Apply")
    def run_terraform_apply(project_slug: str) -> str:
        """
        Executes 'terraform apply -auto-approve' for a specific project.
        WARNING: This creates real cloud resources and may incur costs.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        result = DeploymentTools._run_command("terraform apply -auto-approve -no-color", project_path)
        if result["success"]:
            return f"🚀 Deployment Successful!\nOutputs:\n{result['stdout']}"
        else:
            return f"❌ Deployment Failed with API Error:\n{result['stderr']}\n\nSTDOUT Trace:\n{result['stdout']}"

    @tool("Run Terraform Destroy")
    def run_terraform_destroy(project_slug: str) -> str:
        """
        Executes 'terraform destroy -auto-approve' to clean up infrastructure.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        result = DeploymentTools._run_command("terraform destroy -auto-approve -no-color", project_path)
        if result["success"]:
            return "🧹 Infrastructure successfully destroyed."
        else:
            return f"❌ Destroy Failed:\n{result['stderr']}"

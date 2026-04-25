import os
import subprocess
from crewai.tools import tool

class DeploymentTools:
    
    @staticmethod
    def _run_command(command, cwd):
        """Helper to run shell commands and capture output."""
        try:
            # Support both string and list commands
            if isinstance(command, str):
                cmd_list = command.split()
            else:
                cmd_list = command
            process = subprocess.run(
                cmd_list,
                cwd=cwd,
                capture_output=True,
                text=True
            )
            return {
                "success": process.returncode == 0,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "exit_code": process.returncode
            }
        except Exception as e:
            return {"success": False, "stderr": str(e), "stdout": "", "exit_code": -1}

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
    def run_terraform_plan(project_slug: str, is_destroy: bool = False) -> str:
        """
        Executes 'terraform plan' for a specific project.
        If is_destroy=True, it generates a destruction plan.
        Returns the plan output or detailed error messages.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        # Ensure init is run first
        DeploymentTools._run_command("terraform init -backend=false", project_path)
        
        cmd = "terraform plan -no-color"
        if is_destroy:
            cmd += " -destroy"
            
        result = DeploymentTools._run_command(cmd, project_path)
        log_name = "terraform_plan_destroy" if is_destroy else "terraform_plan"
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, log_name, combined_output)

        if result["success"]:
            return f"✅ Terraform Plan Succeeded{log_msg}:\n{result['stdout']}"
        else:
            return f"❌ Terraform Plan Failed{log_msg}:\n{result['stderr']}"

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
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, "terraform_apply", combined_output)

        if result["success"]:
            return f"🚀 Deployment Successful!{log_msg}\nOutputs:\n{result['stdout']}"
        else:
            return f"❌ Deployment Failed with API Error{log_msg}:\n{result['stderr']}\n\nSTDOUT Trace:\n{result['stdout']}"

    @tool("Run Terraform Destroy")
    def run_terraform_destroy(project_slug: str) -> str:
        """
        Executes 'terraform destroy -auto-approve' to clean up infrastructure.
        """
        project_path = os.path.join("output", project_slug)
        if not os.path.exists(project_path):
            return f"Error: Project directory '{project_path}' not found."

        result = DeploymentTools._run_command("terraform destroy -auto-approve -no-color", project_path)
        combined_output = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"
        log_msg = DeploymentTools._save_log(project_path, "terraform_destroy", combined_output)

        if result["success"]:
            return f"🧹 Infrastructure successfully destroyed.{log_msg}"
        else:
            return f"❌ Destroy Failed{log_msg}:\n{result['stderr']}"

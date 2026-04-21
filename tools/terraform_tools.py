import os
import subprocess
import shutil
from datetime import datetime
from langchain_core.tools import tool

class TerraformTools:

    @tool("Write Terraform File")
    def write_terraform_file(filename: str, content: str, project_slug: str = "workspace") -> str:
        """
        Writes terraform code to a file in a PROJECT-SPECIFIC output directory.
        Args:
            filename (str): The relative path of the file (e.g., 'main.tf' or 'modules/vpc/main.tf').
            content (str): The terraform code to write.
            project_slug (str): The name of the project folder. Defaults to 'workspace'.
        """
        output_base = os.path.join("output", project_slug)
        filepath = os.path.join(output_base, filename)
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Failed to write file {filename}. Error: {str(e)}"

    @tool("Validate Terraform Code")
    def validate_terraform_code(project_slug: str = "workspace") -> str:
        """
        Runs validation in a PROJECT-SPECIFIC output directory.
        """
        output_dir = os.path.join("output", project_slug)
        if not os.path.exists(output_dir):
            return f"No terraform files found in {output_dir}."

        try:
            # Init
            init_process = subprocess.run(
                ["terraform", "init", "-backend=false"],
                cwd=output_dir,
                capture_output=True,
                text=True
            )
            if init_process.returncode != 0:
                return f"Terraform Init Failed:\n{init_process.stderr}"

            # Validate
            validate_process = subprocess.run(
                ["terraform", "validate"],
                cwd=output_dir,
                capture_output=True,
                text=True
            )
            if validate_process.returncode == 0:
                return "Terraform Validate Succeeded! Code is syntactically valid."
            else:
                return f"Terraform Validate Failed:\n{validate_process.stderr}"

        except FileNotFoundError:
            return "Terraform CLI is not installed or not in PATH. Cannot validate code."
        except Exception as e:
            return f"An unexpected error occurred during validation: {str(e)}"

    @tool("Backup Workspace")
    def backup_workspace(project_slug: str) -> str:
        """
        Creates a timestamped backup of the current project workspace.
        Used to support the 'Revert' capability if fix rounds fail.
        """
        src = os.path.join("output", project_slug)
        if not os.path.exists(src):
            return "Workspace does not exist, cannot backup."
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join("output", f".backups", f"{project_slug}_{timestamp}")
        
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(src, dst)
            return f"Backup created at {dst}"
        except Exception as e:
            return f"Backup failed: {str(e)}"

    @tool("Restore Workspace")
    def restore_workspace(project_slug: str, backup_path: str) -> str:
        """
        Restores a project workspace from a specified backup path.
        """
        dst = os.path.join("output", project_slug)
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(backup_path, dst)
            return f"Workspace {project_slug} restored from {backup_path}"
        except Exception as e:
            return f"Restore failed: {str(e)}"


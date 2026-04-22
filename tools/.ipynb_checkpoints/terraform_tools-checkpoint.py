import os
import subprocess
import shutil
from datetime import datetime
from crewai.tools import tool

class TerraformTools:

    @staticmethod
    def _sanitize_slug(slug: str) -> str:
        """Strips 'output/' prefix and leading/trailing slashes to prevent nested directories."""
        if not slug:
            return "workspace"
        # Remove 'output/' or 'output\' prefix if the agent accidentally includes it
        slug = slug.replace("output/", "").replace("output\\", "")
        # Remove any leading/trailing slashes
        return slug.strip("/\\")

    @staticmethod
    def _write_terraform_file(filename: str, content: str, project_slug: str = "workspace") -> str:
        # Sanitize the project_slug to avoid unwanted characters or paths
        slug = TerraformTools._sanitize_slug(project_slug)
        # Create the project folder inside 'output'
        output_base = os.path.join("output", slug)  # This is the correct location for the project directory
    
    # Create the full file path
        filepath = os.path.join(output_base, filename)
        try:
            # Create the project folder if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
            # Write the content to the file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {filepath} (Project: {slug})"
        except Exception as e:
            return f"Failed to write file {filename}. Error: {str(e)}"

    @staticmethod
    def _validate_terraform_code(project_slug: str = "workspace") -> str:
        slug = TerraformTools._sanitize_slug(project_slug)
        output_dir = os.path.join("output", slug)
        if not os.path.exists(output_dir):
            return f"No terraform files found in {output_dir}. Are you sure the slug is correct?"

        try:
            # Init
            init_process = subprocess.run(
                ["terraform", "init", "-backend=false"],
                cwd=output_dir,
                capture_output=True,
                text=True
            )
            if init_process.returncode != 0:
                return f"Terraform Init Failed for project '{slug}':\n{init_process.stderr}"

            # Validate
            validate_process = subprocess.run(
                ["terraform", "validate"],
                cwd=output_dir,
                capture_output=True,
                text=True
            )
            if validate_process.returncode == 0:
                return f"Terraform Validate Succeeded for project '{slug}'! Code is syntactically valid."
            else:
                return f"Terraform Validate Failed for project '{slug}':\n{validate_process.stderr}"

        except FileNotFoundError:
            return "Terraform CLI is not installed or not in PATH. Cannot validate code."
        except Exception as e:
            return f"An unexpected error occurred during validation: {str(e)}"

    @staticmethod
    def _backup_workspace(project_slug: str) -> str:
        slug = TerraformTools._sanitize_slug(project_slug)
        src = os.path.join("output", slug)
        if not os.path.exists(src):
            return f"Workspace '{slug}' does not exist, cannot backup."
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join("output", f".backups", f"{slug}_{timestamp}")
        
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copytree(src, dst)
            return f"Backup created at {dst}"
        except Exception as e:
            return f"Backup failed: {str(e)}"

    @staticmethod
    def _restore_workspace(project_slug: str, backup_path: str) -> str:
        slug = TerraformTools._sanitize_slug(project_slug)
        dst = os.path.join("output", slug)
        try:
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(backup_path, dst)
            return f"Workspace {slug} restored from {backup_path}"
        except Exception as e:
            return f"Restore failed: {str(e)}"

    # --- Tool Wrappers for CrewAI ---

    @tool("Write Terraform File")
    def write_terraform_file(filename: str, content: str, project_slug: str = "workspace") -> str:
        """Writes terraform code to a file. Provide ONLY the project name (slug) for project_slug, e.g. 'my-vpc'."""
        return TerraformTools._write_terraform_file(filename, content, project_slug)

    @tool("Validate Terraform Code")
    def validate_terraform_code(project_slug: str = "workspace") -> str:
        """Validates terraform code. Provide ONLY the project name (slug) for project_slug, e.g. 'my-vpc'."""
        return TerraformTools._validate_terraform_code(project_slug)

    @tool("Backup Workspace")
    def backup_workspace(project_slug: str) -> str:
        """Creates a backup of a project workspace. Provide ONLY the project name (slug)."""
        return TerraformTools._backup_workspace(project_slug)

    @tool("Restore Workspace")
    def restore_workspace(project_slug: str, backup_path: str) -> str:
        """Restores a project workspace. Provide ONLY the project name (slug)."""
        return TerraformTools._restore_workspace(project_slug, backup_path)

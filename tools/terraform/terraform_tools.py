import os
import re
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
        
        # Also sanitize the filename - if it starts with 'output/' or the slug itself, strip it
        clean_filename = filename.replace("output/", "").replace("output\\", "")
        clean_filename = clean_filename.replace(f"{slug}/", "").replace(f"{slug}\\", "")
        clean_filename = clean_filename.strip("/\\")

        # Create the project folder inside 'output'
        output_base = os.path.join("output", slug)
    
        # Create the full file path
        filepath = os.path.join(output_base, clean_filename)

        # ── Sanitize HCL content (fix common LLM hallucinations) ──
        if filepath.endswith(".tf"):
            content = TerraformTools._sanitize_hcl(content)

        try:
            # Create the project folder if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
            # Write the content to the file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Auto-format with terraform fmt (best-effort, non-blocking)
            TerraformTools._auto_fmt(filepath)

            return f"Successfully wrote to {filepath} (Project: {slug})"
        except Exception as e:
            return f"Failed to write file {filename}. Error: {str(e)}"

    @staticmethod
    def _sanitize_hcl(content: str) -> str:
        """Fix common LLM hallucinations in HCL output.

        1. Replace semicolons with newlines (LLMs write single-line blocks)
        2. Ensure closing braces are on their own lines
        3. Ensure arguments before closing braces end with newlines
        """
        # Replace ; with newline (the #1 LLM HCL error)
        content = content.replace(";", "\n")

        # Ensure } is on its own line (not glued to the previous argument)
        # Match: non-whitespace followed by } on the same line
        content = re.sub(r'(\S)\s*\}', r'\1\n}', content)

        # Clean up any triple+ newlines
        content = re.sub(r'\n{3,}', '\n\n', content)

        return content

    @staticmethod
    def _auto_fmt(filepath: str) -> None:
        """Best-effort terraform fmt on a single file. Silent on failure."""
        try:
            directory = os.path.dirname(filepath)
            subprocess.run(
                ["terraform", "fmt", os.path.basename(filepath)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            pass  # fmt is optional — don't block the pipeline

    @staticmethod
    def _validate_terraform_code(project_slug: str = "workspace") -> str:
        slug = TerraformTools._sanitize_slug(project_slug)
        output_dir = os.path.join("output", slug)
        if not os.path.exists(output_dir):
            return f"No terraform files found in {output_dir}. Are you sure the slug is correct?"

        try:
            # Init (MUST run before validate so modules are installed)
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

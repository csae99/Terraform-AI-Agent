import os
import subprocess
from langchain.tools import tool

class TerraformTools:

    @tool("Write Terraform File")
    def write_terraform_file(filename: str, content: str) -> str:
        """
        Writes terraform code to a file in the output directory.
        The filename can include subdirectories (e.g., 'my-project/main.tf' or 'my-project/modules/vpc/main.tf').
        Args:
            filename (str): The relative path of the file within the output directory.
            content (str): The terraform code to write.
        Returns:
            str: A success or error message.
        """
        output_base = "output"
        filepath = os.path.join(output_base, filename)
        
        try:
            # Create directories recursively
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, "w") as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
        except Exception as e:
            return f"Failed to write file {filename}. Error: {str(e)}"

    @tool("Validate Terraform Code")
    def validate_terraform_code(dummy: str = None) -> str:
        """
        Runs `terraform init -backend=false` and `terraform validate` in the output directory 
        to verify if the generated terraform code has syntax errors.
        Args:
            dummy (str): Not used, but required by some tool interfaces.
        Returns:
            str: The output of the validation command, highlighting any syntax errors.
        """
        output_dir = "output"
        if not os.path.exists(output_dir):
            return "No terraform files have been written yet. Cannot validate."

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

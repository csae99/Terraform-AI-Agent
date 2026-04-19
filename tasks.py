from crewai import Task

class TerraformTasks:

    def design_architecture_task(self, agent, requirement):
        return Task(
            description=f'Analyze the following infrastructure requirement and design a complete architecture.\nRequirement: {requirement}\n'
                        f'Specify the provider, resources needed, networking setup, and any variables or outputs required.',
            expected_output='A detailed architecture document specifying cloud provider, resources, networking, and configuration details.',
            agent=agent
        )

    def write_terraform_task(self, agent):
        return Task(
            description='Using the architecture document from the architect, write the necessary Terraform files.\n'
                        'IMPORTANT: You must use the `Write Terraform File` tool to save your files (e.g. main.tf, variables.tf, outputs.tf, providers.tf) in the output directory.\n'
                        'Ensure you use best practices and modern Terraform syntax.',
            expected_output='Written `.tf` files in the output directory. A summary describing the created files.',
            agent=agent
        )

    def validate_and_review_task(self, agent):
        return Task(
            description='Review the Terraform files written by the developer in the output directory.\n'
                        '1. Run the `Validate Terraform Code` tool to check for syntax errors.\n'
                        '2. If there are syntax errors, use the `Write Terraform File` tool to correct them.\n'
                        '3. Ensure basic security practices are met (e.g., no public overly-permissive ingress rules).',
            expected_output='A final review report stating that the Terraform code is syntactically valid and complies with security standards.',
            agent=agent
        )

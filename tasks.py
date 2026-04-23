from crewai import Task

class TerraformTasks:

    def design_architecture_task(self, agent, requirement):
        return Task(
            description=f'Analyze the following infrastructure requirement and design a MINIMAL architecture.\n'
                        f'Requirement: {requirement}\n'
                        'IMPORTANT: DO NOT add NAT Gateways, Private Subnets, or Multi-AZ unless explicitly requested.\n'
                        'If the user asks for a Public Subnet, provide ONLY an IGW and the requested subnet.\n'
                        'You MUST specify a short, unique `project_slug` (e.g. "my-app-vpc") as the first line of your response.',
            expected_output='A detailed architecture document. The first line must be: PROJECT_SLUG: <slug>',
            agent=agent
        )

    def write_terraform_task(self, agent, project_slug):
        return Task(
            description=f'Based on the Architect\'s design, implement the Terraform project: {project_slug}.\n'
                        '1. You MUST use the `write_terraform_file` tool for every single file.\n'
                        '2. Structure: Root `main.tf` calling modules in `modules/vpc/`, `modules/security/`, etc.\n'
                        '3. Do NOT just output text. If you do not call the tool, the files will not exist and the task fails.\n'
                        '4. You MUST create a `README.md` in the project ROOT (not in modules) explaining the setup.\n'
                        f'Project Slug: {project_slug}',
            expected_output=f'A fully populated modular project in output/{project_slug}/ consisting of multiple .tf files.',
            agent=agent
        )

    def audit_task(self, agent, project_slug):
        return Task(
            description=f'Review the Terraform code in the `{project_slug}` workspace for security and syntax.\n'
                        'Use the `Validate Terraform Code` tool.',
            expected_output='A report detailing any syntax errors or security risks.',
            agent=agent
        )

    def financial_analysis_task(self, agent, project_slug, budget=100.0):
        return Task(
            description=f'Analyze the projected costs for the `{project_slug}` workspace.\n'
                        f'1. Use `get_monthly_cost` to get the total estimated spend.\n'
                        f'2. Use `generate_financial_report` to create the detailed breakdown.\n'
                        f'3. Compare the total cost against the budget: ${budget}.\n'
                        f'4. If the cost exceeds the budget, provide optimization suggestions.',
            expected_output='A cost analysis summary with budget status.',
            agent=agent
        )

    def deployment_task(self, agent, project_slug):
        return Task(
            description=f'Execute the live deployment for the `{project_slug}` workspace.\n'
                        f'1. Run `run_terraform_plan` to verify the changes.\n'
                        f'2. If the plan output shows resources to be created (e.g. "Plan: 3 to add"), '
                        f'you MUST IMMEDIATELY run `run_terraform_apply` to provision them.\n'
                        f'3. DO NOT repeat the plan more than once. If it looks correct, apply it.\n'
                        f'4. If any API errors occur, report the EXACT error log for self-healing.\n'
                        f'5. Return the final output (Bucket Name, ARN, etc.) if successful.',
            expected_output='A deployment status report confirming the resources are LIVE on AWS.',
            agent=agent
        )

    def decommissioning_task(self, agent, project_slug):
        return Task(
            description=f'Permanently destroy all infrastructure in the `{project_slug}` workspace.\n'
                        f'1. Use the `run_terraform_destroy` tool.\n'
                        f'2. Ensure all resources are successfully removed.\n'
                        f'3. If any "DependencyViolation" or "BucketNotEmpty" errors occur, '
                        f'report the EXACT log for remediation.',
            expected_output='A confirmation report that the infrastructure has been successfully destroyed.',
            agent=agent
        )

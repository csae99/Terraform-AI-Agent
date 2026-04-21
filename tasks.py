from crewai import Task

class TerraformTasks:

    def design_architecture_task(self, agent, requirement):
        return Task(
            description=f'Analyze the following infrastructure requirement and design a complete architecture.\nRequirement: {requirement}\n'
                        f'IMPORTANT: You MUST specify a short, unique `project_slug` (e.g. "my-app-vpc") as the first line of your response.',
            expected_output='A detailed architecture document. The first line must be: PROJECT_SLUG: <slug>',
            agent=agent
        )

    def write_terraform_task(self, agent, project_slug):
        return Task(
            description=f'Using the architecture design, write the Terraform files for project: {project_slug}.\n'
                        'Use the `Write Terraform File` tool and always provide the `project_slug` parameter.',
            expected_output=f'Written `.tf` files in output/{project_slug}/.',
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
            expected_output='A summary of the monthly cost and whether it fits the budget.',
            agent=agent
        )

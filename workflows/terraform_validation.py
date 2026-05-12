from crewai import Task

class TerraformValidationTasks:

    @staticmethod
    def audit_task(agent, project_slug):
        return Task(
            description=f'Review the Terraform code in the `{project_slug}` workspace for security and syntax.\n'
                        'Use the `Validate Terraform Code` tool.',
            expected_output='A report detailing any syntax errors or security risks.',
            agent=agent
        )

    @staticmethod
    def financial_analysis_task(agent, project_slug, budget=100.0):
        return Task(
            description=f'Analyze the projected costs for the `{project_slug}` workspace.\n'
                        f'1. Use `get_monthly_cost` to get the total estimated spend.\n'
                        f'2. Use `generate_financial_report` to create the detailed breakdown.\n'
                        f'3. Compare the total cost against the budget: ${budget}.\n'
                        f'4. If the cost exceeds the budget, provide optimization suggestions.',
            expected_output='A cost analysis summary with budget status.',
            agent=agent
        )

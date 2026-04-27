from crewai import Agent
from tools.terraform_tools import TerraformTools
from llm_config import get_llm

class TerraformAgents:
    def __init__(self, model_name=None, api_key=None):
        self.llm = get_llm(model_name, api_key)


    def cloud_architect(self):
        return Agent(
            role='Universal Cloud Architect',
            goal='Design the minimum viable infrastructure using the EXACT provider requested (Local, AWS, Azure, GCP).',
            backstory='You are a multi-provider expert. If a user asks for a "Local File", you MUST use the '
                      'Terraform "local" provider. DO NOT default to AWS if the user asks for local resources. '
                      'You map prompts to the specific provider requested. Avoid architectural noise and '
                      'extra resources not mentioned in the prompt.',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def terraform_developer(self):
        return Agent(
            role='Senior Terraform Developer',
            goal='Implement ONLY the resources designed by the Architect. DO NOT add unrequested noise.',
            backstory='You are a precision coder. You MUST NOT add NAT Gateways, VPCs, or Security Groups '
                      'unless they are explicitly in the Architect\'s design. If the Architect asks for '
                      'a "Local Provider", do NOT add AWS resources. Your job is to be a 1:1 mirror of '
                      'the design, regardless of the provider (Local, AWS, etc.).',
            tools=[TerraformTools.write_terraform_file],
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def security_reviewer(self):
        return Agent(
            role='Security & Compliance Reviewer',
            goal='Review Terraform code for security best practices and validate syntax.',
            backstory='You are a strict security engineer. You ensure no open ports remain without reason, '
                      'encryption is enabled, and syntax is perfectly valid. You use the `Validate Terraform Code` tool '
                      'and specify the `project_slug`. You DO NOT write files; you only provide feedback.',
            tools=[TerraformTools.validate_terraform_code],
            verbose=True,
            allow_delegation=False, # Disabled to prevent circular loops
            llm=self.llm
        )

    def finops_specialist(self):
        from tools.financial_tools import CostEstimator
        return Agent(
            role='FinOps Specialist',
            goal='Audit infrastructure for cost efficiency and suggest budget-friendly alternatives.',
            backstory='You are an expert in cloud economics. You MUST ONLY report costs that are returned by your tools. '
                      'DO NOT speculate or hallucinate costs (like Azure costs for AWS resources). '
                      'If the tool returns 0, you must report 0 and explain that the current configuration has no billed resources.',
            tools=[CostEstimator.get_monthly_cost, CostEstimator.generate_financial_report],
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def deployment_specialist(self):
        from tools.deployment_tools import DeploymentTools
        return Agent(
            role='Deployment Specialist',
            goal='Execute live cloud deployments and decommissioning tasks.',
            backstory='You are a high-stakes DevOps engineer. Your job is to run `terraform apply` or '
                      '`terraform destroy` and ensure the environment matches the goal. If you encounter '
                      'a cloud error, you MUST explain the error clearly so the Developer can fix it. '
                      'You are responsible for the entire infrastructure lifecycle.',
            tools=[DeploymentTools.run_terraform_plan, 
                   DeploymentTools.run_terraform_apply,
                   DeploymentTools.run_terraform_destroy,
                   DeploymentTools.detect_drift],

            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

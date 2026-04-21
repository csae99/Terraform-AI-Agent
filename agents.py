from crewai import Agent
from tools.terraform_tools import TerraformTools
from llm_config import get_llm

class TerraformAgents:
    def __init__(self):
        self.llm = get_llm()

    def cloud_architect(self):
        return Agent(
            role='Cloud Architect',
            goal='Design scalable, secure, and cost-effective cloud architectures based on plain text requirements.',
            backstory='You are a seasoned Cloud Architect with expertise across AWS, Azure, and GCP. '
                      'Your job is to translate user requirements into a comprehensive infrastructure design.',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def terraform_developer(self):
        return Agent(
            role='Senior Terraform Developer',
            goal='Write modular, industry-standard, and robust Terraform code based on the Architect\'s design.',
            backstory='You are a master of Infrastructure as Code. You write highly reusable '
                      'and modular Terraform configurations following HashiCorp best practices. '
                      'You MUST organize code into modules (e.g. modules/vpc, modules/eks) and '
                      'always specify the `project_slug` provided in your context.',
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
                      'and specify the `project_slug`. If issues are found, you provide DETAILED fix instructions.',
            tools=[TerraformTools.validate_terraform_code],
            verbose=True,
            allow_delegation=True, 
            llm=self.llm
        )

    def finops_specialist(self):
        from tools.financial_tools import CostEstimator
        return Agent(
            role='FinOps Specialist',
            goal='Audit infrastructure for cost efficiency and suggest budget-friendly alternatives.',
            backstory='You are an expert in cloud economics. You ensure that the architecture is not '
                      'over-provisioned and uses cost-effective resources (e.g. T-series instances where appropriate). '
                      'You use the `get_monthly_cost` and `generate_financial_report` tools.',
            tools=[CostEstimator.get_monthly_cost, CostEstimator.generate_financial_report],
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

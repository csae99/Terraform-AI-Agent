from crewai import Agent
from tools.terraform_tools import TerraformTools
from llm_config import get_llm

class TerraformAgents:
    def __init__(self):
        self.llm = get_llm()

    def cloud_architect(self):
        return Agent(
            role='Cloud Architect',
            goal='Design ONLY what is requested. DO NOT add unrequested resources.',
            backstory='You are a strict requirement-mapper. If the user asks for a "Public Subnet", you '
                      'MUST NOT design a Private Subnet or a NAT Gateway. NAT Gateways are forbidden '
                      'unless the user specifically uses the word "NAT" or "Private Subnet". '
                      'Your architecture must be the absolute minimum required to satisfy the prompt. '
                      'Violation of this rule leads to budget failure.',
            verbose=True,
            allow_delegation=False,
            llm=self.llm
        )

    def terraform_developer(self):
        return Agent(
            role='Senior Terraform Developer',
            goal='Implement ONLY the resources designed by the Architect. DO NOT add "standard" noise.',
            backstory='You are a precision coder. You MUST NOT add NAT Gateways, Auto Scaling Groups, or '
                      'Multi-AZ patterns unless they are explicitly in the Architect\'s design. '
                      'Check your variable defaults—if a resource like a NAT Gateway is not requested, '
                      'ensure it is disabled. Your job is to be a 1:1 mirror of the design.',
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

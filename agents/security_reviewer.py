from crewai import Agent
from agents.base import BaseAgent
from tools.terraform.terraform_tools import TerraformTools

class SecurityReviewer(BaseAgent):
    def get_agent(self):
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

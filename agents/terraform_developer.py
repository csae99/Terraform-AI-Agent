from crewai import Agent
from agents.base import BaseAgent
from tools.terraform.terraform_tools import TerraformTools

class TerraformDeveloper(BaseAgent):
    def get_agent(self):
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

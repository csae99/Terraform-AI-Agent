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
            goal='Write modular, standard, and robust Terraform code based on the Architect\\'s design.',
            backstory='You are a master of Infrastructure as Code. You write highly reusable '
                      'and maintainable Terraform configurations. You split code logically into '
                      'main.tf, variables.tf, outputs.tf, and providers.tf.',
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
                      'encryption is enabled, and syntax is perfectly valid. You will validate '
                      'the generated code to ensure it complies with Terraform syntactical rules.',
            tools=[TerraformTools.validate_terraform_code, TerraformTools.write_terraform_file],
            verbose=True,
            allow_delegation=True, # Allowed to kick back to dev if there's an issue
            llm=self.llm
        )

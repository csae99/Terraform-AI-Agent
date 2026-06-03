from crewai import Agent
from agents.base import BaseAgent
from tools.terraform.terraform_tools import TerraformTools

class TerraformDeveloper(BaseAgent):
    def get_agent(self):
        return Agent(
            role='Senior Terraform Developer',
            goal='Implement EVERY file from the Architect design EXCLUSIVELY by using the `Write Terraform File` tool. '
                 'You MUST write ALL module files (main.tf, variables.tf, outputs.tf) for EACH module. '
                 'Do NOT stop until every module directory and every file is created.',
            backstory='You are a precision infrastructure coder. You write production-grade, '
                      'multi-file Terraform projects. '
                      'CRITICAL RULE: You CANNOT write code in plain text. You MUST use the `Write Terraform File` tool '
                      'for EVERY SINGLE FILE. If you do not use the tool, the file is not created, and you fail. '
                      'For every module referenced in root main.tf, you MUST create the full module directory with '
                      'main.tf, variables.tf, and outputs.tf. '
                      'You never stop early — if the architecture has 4 modules, you write at least 12 files '
                      'plus root files. Incomplete projects are failures.',
            tools=[TerraformTools.write_terraform_file, TerraformTools.search_terraform_documentation],
            verbose=True,
            allow_delegation=False,
            max_iter=30,
            llm=self.llm
        )


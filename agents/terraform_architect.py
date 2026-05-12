from crewai import Agent
from agents.base import BaseAgent

class TerraformArchitect(BaseAgent):
    def get_agent(self):
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

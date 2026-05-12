from crewai import Agent
from agents.base import BaseAgent
from tools.deployment.deployment_tools import DeploymentTools

class DeploymentPlanner(BaseAgent):
    def get_agent(self):
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

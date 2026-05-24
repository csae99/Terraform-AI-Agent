from crewai import Agent
from agents.base import BaseAgent
from tools.deployment.testing_tools import TestingTools

class TestingAgent(BaseAgent):
    def get_agent(self) -> Agent:
        return Agent(
            role='Infrastructure QA and Behavior Validator',
            goal='Validate that deployed cloud resources are active, reachable, and behaving correctly by performing smoke tests.',
            backstory='You are a high-reliability QA engineer specializing in cloud infrastructure validation. '
                      'After resources are deployed, you test their real-world functionality using HTTP probes and API calls. '
                      'You report the precise results of each test to ensure that the infrastructure is not just provisioned, '
                      'but actually operational and healthy.',
            tools=[
                TestingTools.verify_http_endpoint,
                TestingTools.verify_s3_bucket,
                TestingTools.verify_aws_resource_exists
            ],
            verbose=True,
            allow_delegation=False,
            max_iter=10,
            llm=self.llm
        )

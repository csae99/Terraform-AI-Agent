from crewai import Agent
from agents.base import BaseAgent
from tools.finance.cost_estimation import CostEstimator

class CostOptimizer(BaseAgent):
    def get_agent(self):
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

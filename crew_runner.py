import sys
from crewai import Crew, Process
from agents import TerraformAgents
from tasks import TerraformTasks

def main():
    if len(sys.argv) < 2:
        print("Usage: python crew_runner.py \\"<your infrastructure requirement>\\"")
        print("Example: python crew_runner.py \\"I need a scalable VPC in AWS with two public subnets.\\"")
        sys.exit(1)

    requirement = sys.argv[1]
    print(f"\\n🚀 Initiating Terraform AI Agent for requirement: '{requirement}'\\n")

    # Instantiate Agents & Tasks classes
    agents = TerraformAgents()
    tasks = TerraformTasks()

    # Create Agents
    cloud_architect = agents.cloud_architect()
    tf_developer = agents.terraform_developer()
    security_reviewer = agents.security_reviewer()

    # Create Tasks
    architecture_task = tasks.design_architecture_task(cloud_architect, requirement)
    coding_task = tasks.write_terraform_task(tf_developer)
    review_task = tasks.validate_and_review_task(security_reviewer)

    # Form the Crew
    terraform_crew = Crew(
        agents=[cloud_architect, tf_developer, security_reviewer],
        tasks=[architecture_task, coding_task, review_task],
        process=Process.sequential,  # Run sequentially: Architect -> Dev -> Reviewer
        verbose=True
    )

    # Execute workflow
    result = terraform_crew.kickoff()

    print("\\n=======================================================")
    print("✅ Terraform AI Agent Workflow Completed!")
    print("=======================================================")
    print(result)
    print("=======================================================\\n")
    print("Check the 'output/' directory for your generated Terraform files.")

if __name__ == "__main__":
    main()

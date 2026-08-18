from crewai import Task
from tools.gitops.gitops_tools import GitOpsTools

class GitOpsWorkflowTasks:
    @staticmethod
    def create_gitops_pr_task(agent, slug: str, repo_url: str, target_branch: str = "main",
                              prompt: str = "", cost_summary: str = "", audit_summary: str = "",
                              mermaid_diagram: str = "") -> Task:
        """
        Creates a CrewAI task for the GitOpsCoordinator to review generated IaC,
        construct release metadata, and formulate a Pull Request description.
        """
        return Task(
            description=(
                f"You are the GitOps & Release Coordinator for workspace '{slug}'.\n"
                f"Review the generated infrastructure for requirement: '{prompt}'.\n"
                f"Prepare a release Pull Request targeting branch '{target_branch}' on repository '{repo_url}'.\n"
                f"Ensure the PR contains an Executive Summary, Visual Mermaid Topology, FinOps Cost breakdown, "
                f"and Security verification compliance."
            ),
            expected_output=(
                "A clean, professional Pull Request title and Markdown description formatted "
                "with badges, topologies, and verification checkboxes."
            ),
            agent=agent
        )

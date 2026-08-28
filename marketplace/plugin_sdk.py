from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class BasePlugin(ABC):
    """
    Abstract Base Class for all Terraform AI Agent Marketplace Plugins.
    Provides standard lifecycle hooks across the full platform pipeline:
    Initialization -> Pre/Post Generation -> Pre/Post PR -> Pre/Post Apply -> Pre/Post QA -> On Failure.
    """

    def __init__(self, name: str, version: str = "1.0.0", description: str = "", minimum_platform_version: str = "14.0"):
        self.name = name
        self.version = version
        self.description = description
        self.minimum_platform_version = minimum_platform_version
        self.config: Dict[str, Any] = {}
        self.enabled: bool = True

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Called when plugin is loaded/configured."""
        if config:
            self.config.update(config)
        return True

    # ── 1. Generation Lifecycle Hooks ─────────────────────────────
    def pre_generation(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before architecture synthesis and code generation starts."""
        return context

    def post_generation(self, hcl_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed after HCL code is synthesized by developer agents."""
        return {"hcl_code": hcl_code, "context": context}

    # Backwards compatibility aliases
    def pre_plan_hook(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.pre_generation(prompt, context)

    def post_plan_hook(self, hcl_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return self.post_generation(hcl_code, context)

    # ── 2. Validation Hook ────────────────────────────────────────
    def validate(self, hcl_code: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Custom validation rule executed alongside Checkov and OPA."""
        return {"valid": True, "plugin": self.name, "issues": []}

    # ── 3. GitOps PR Lifecycle Hooks ──────────────────────────────
    def pre_pr(self, branch_name: str, pr_payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before opening a GitOps Pull Request."""
        return {"branch_name": branch_name, "pr_payload": pr_payload, "context": context}

    def post_pr(self, pr_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed after a GitOps Pull Request is successfully opened."""
        return {"pr_result": pr_result, "context": context}

    # ── 4. Deployment Lifecycle Hooks ─────────────────────────────
    def pre_apply(self, plan_summary: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before executing terraform / opentofu apply."""
        return {"plan_summary": plan_summary, "context": context}

    def post_apply(self, apply_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed after terraform / opentofu apply completes."""
        return {"apply_result": apply_result, "context": context}

    # ── 5. QA & Smoke Testing Lifecycle Hooks ─────────────────────
    def pre_qa(self, target_resources: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before post-deploy behavior validation tests run."""
        return {"target_resources": target_resources, "context": context}

    def post_qa(self, qa_report: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed after QA smoke tests complete."""
        return {"qa_report": qa_report, "context": context}

    # ── 6. Incident & Error Handling Hook ─────────────────────────
    def on_failure(self, error: str, stage: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed when any pipeline stage or agent task encounters an error."""
        return {"error": error, "stage": stage, "context": context}

    def teardown(self) -> None:
        """Called when plugin is unloaded or destroyed."""
        pass


class CustomToolPlugin(BasePlugin):
    """Plugin type that exposes a custom tool/function to agents."""

    @abstractmethod
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the specific tool provided by this plugin."""
        pass


class CustomAgentPlugin(BasePlugin):
    """Plugin type that registers a specialized autonomous agent."""

    def __init__(self, name: str, role: str, goal: str, backstory: str, version: str = "1.0.0"):
        super().__init__(name=name, version=version, description=goal)
        self.role = role
        self.goal = goal
        self.backstory = backstory

    @abstractmethod
    def run_agent_task(self, task_input: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the specialized agent's reasoning task."""
        pass

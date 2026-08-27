from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class BasePlugin(ABC):
    """
    Abstract Base Class for all Terraform AI Agent Marketplace Plugins.
    Provides standard lifecycle hooks for initialization, pre/post planning, validation, and teardown.
    """

    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.config: Dict[str, Any] = {}
        self.enabled: bool = True

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Called when plugin is loaded/configured."""
        if config:
            self.config.update(config)
        return True

    def pre_plan_hook(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed before architecture planning starts."""
        return context

    def post_plan_hook(self, hcl_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Hook executed after HCL code is synthesized."""
        return {"hcl_code": hcl_code, "context": context}

    def validate(self, hcl_code: str) -> Dict[str, Any]:
        """Custom validation rule executed alongside Checkov and OPA."""
        return {"valid": True, "plugin": self.name, "issues": []}

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

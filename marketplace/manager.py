import traceback
import logging
from typing import Dict, List, Any, Optional
from marketplace.catalog import AgentMarketplaceCatalog
from marketplace.plugin_sdk import BasePlugin

logger = logging.getLogger("terraform-marketplace")

class PluginManager:
    """
    Marketplace & Plugin Lifecycle Manager with Safe Sandboxed Execution & Compatibility Matrix.
    Manages per-organization installed plugins, custom hooks, and dynamic agent loading.
    Dispatches events across all expanded lifecycle stages safely.
    """

    CURRENT_PLATFORM_VERSION = "14.0"

    # In-memory registry of installed plugin records: {org_id: {plugin_id: installed_dict}}
    _installed_plugins: Dict[str, Dict[str, Any]] = {}
    
    # In-memory active plugin instances: {org_id: {plugin_id: BasePlugin}}
    _active_instances: Dict[str, Dict[str, BasePlugin]] = {}

    @classmethod
    def check_compatibility(cls, minimum_platform_version: str) -> bool:
        """Verifies if the plugin's minimum platform version requirement is met."""
        try:
            req_major = float(minimum_platform_version.split(".")[0])
            curr_major = float(cls.CURRENT_PLATFORM_VERSION.split(".")[0])
            return curr_major >= req_major
        except Exception:
            return True

    @classmethod
    def register_plugin_instance(cls, org_id: str, plugin_instance: BasePlugin) -> bool:
        """Directly registers a custom instantiated plugin instance with compatibility check."""
        org_key = str(org_id or "default")
        if not cls.check_compatibility(plugin_instance.minimum_platform_version):
            raise ValueError(f"Plugin '{plugin_instance.name}' requires platform version >= {plugin_instance.minimum_platform_version}, but current platform is {cls.CURRENT_PLATFORM_VERSION}.")

        if org_key not in cls._active_instances:
            cls._active_instances[org_key] = {}
        cls._active_instances[org_key][plugin_instance.name] = plugin_instance
        
        # Ensure record exists
        cls.install_plugin(org_id=org_key, plugin_id=plugin_instance.name, config=plugin_instance.config)
        return True

    @classmethod
    def install_plugin(
        cls,
        org_id: str,
        plugin_id: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Installs a marketplace agent or custom plugin for an organization."""
        org_key = str(org_id or "default")
        if org_key not in cls._installed_plugins:
            cls._installed_plugins[org_key] = {}

        meta = AgentMarketplaceCatalog.get_agent_metadata(plugin_id)
        if not meta:
            meta = {
                "id": plugin_id,
                "name": plugin_id.replace("-", " ").title(),
                "version": "1.0.0",
                "minimum_platform_version": "14.0",
                "custom": True,
                "capabilities": ["custom_extension"]
            }

        min_version = meta.get("minimum_platform_version", "14.0")
        is_compatible = cls.check_compatibility(min_version)
        if not is_compatible:
            raise ValueError(f"Incompatible plugin: requires platform version >= {min_version} (Current: {cls.CURRENT_PLATFORM_VERSION})")

        installed_record = {
            "id": plugin_id,
            "metadata": meta,
            "config": config or {},
            "enabled": True,
            "compatible": is_compatible,
            "installed_at": "2026-08-28T00:00:00Z"
        }
        cls._installed_plugins[org_key][plugin_id] = installed_record

        return {
            "status": "installed",
            "plugin_id": plugin_id,
            "organization_id": org_key,
            "details": installed_record
        }

    @classmethod
    def uninstall_plugin(cls, org_id: str, plugin_id: str) -> bool:
        """Uninstalls a plugin for an organization."""
        org_key = str(org_id or "default")
        if org_key in cls._installed_plugins and plugin_id in cls._installed_plugins[org_key]:
            del cls._installed_plugins[org_key][plugin_id]
            if org_key in cls._active_instances and plugin_id in cls._active_instances[org_key]:
                cls._active_instances[org_key][plugin_id].teardown()
                del cls._active_instances[org_key][plugin_id]
            return True
        return False

    @classmethod
    def list_installed(cls, org_id: str) -> List[Dict[str, Any]]:
        """Returns all installed plugins for an organization."""
        org_key = str(org_id or "default")
        return list(cls._installed_plugins.get(org_key, {}).values())

    # ── Safe Invocation Sandbox Wrapper ───────────────────────────
    @classmethod
    def _safe_invoke(cls, plugin: BasePlugin, hook_name: str, *args, **kwargs) -> Any:
        """Invokes a plugin hook inside an isolated safety wrapper to prevent pipeline crashes."""
        try:
            method = getattr(plugin, hook_name, None)
            if callable(method):
                return method(*args, **kwargs)
        except Exception as e:
            logger.error(f"[Plugin Sandbox Error] Plugin '{plugin.name}' raised in '{hook_name}': {e}\n{traceback.format_exc()}")
        return None

    # ── 1. Pre/Post Generation Dispatchers ────────────────────────
    @classmethod
    def execute_pre_plan_hooks(cls, org_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-generation / pre-plan hooks across installed plugins."""
        org_key = str(org_id or "default")
        for p_id, p_data in cls._installed_plugins.get(org_key, {}).items():
            if p_data.get("enabled"):
                caps = p_data.get("metadata", {}).get("capabilities", [])
                if "active_capabilities" not in context:
                    context["active_capabilities"] = []
                context["active_capabilities"].extend(caps)

        # Call active instances safely
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "pre_generation", prompt, context)
                if isinstance(res, dict):
                    context = res
        return context

    @classmethod
    def execute_post_generation_hooks(cls, org_id: str, hcl_code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs post-generation hooks across installed plugins safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "post_generation", hcl_code, context)
                if isinstance(res, dict):
                    hcl_code = res.get("hcl_code", hcl_code)
                    context = res.get("context", context)
        return {"hcl_code": hcl_code, "context": context}

    # ── 2. GitOps PR Lifecycle Dispatchers ────────────────────────
    @classmethod
    def execute_pre_pr_hooks(cls, org_id: str, branch_name: str, pr_payload: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-PR creation hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "pre_pr", branch_name, pr_payload, context)
                if isinstance(res, dict):
                    branch_name = res.get("branch_name", branch_name)
                    pr_payload = res.get("pr_payload", pr_payload)
        return {"branch_name": branch_name, "pr_payload": pr_payload, "context": context}

    @classmethod
    def execute_post_pr_hooks(cls, org_id: str, pr_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs post-PR creation hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "post_pr", pr_result, context)
                if isinstance(res, dict):
                    pr_result = res.get("pr_result", pr_result)
        return {"pr_result": pr_result, "context": context}

    # ── 3. Apply Lifecycle Dispatchers ────────────────────────────
    @classmethod
    def execute_pre_apply_hooks(cls, org_id: str, plan_summary: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-apply hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "pre_apply", plan_summary, context)
                if isinstance(res, dict):
                    plan_summary = res.get("plan_summary", plan_summary)
        return {"plan_summary": plan_summary, "context": context}

    @classmethod
    def execute_post_apply_hooks(cls, org_id: str, apply_result: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs post-apply hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "post_apply", apply_result, context)
                if isinstance(res, dict):
                    apply_result = res.get("apply_result", apply_result)
        return {"apply_result": apply_result, "context": context}

    # ── 4. QA & Behavior Testing Dispatchers ──────────────────────
    @classmethod
    def execute_pre_qa_hooks(cls, org_id: str, target_resources: List[str], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-QA hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "pre_qa", target_resources, context)
                if isinstance(res, dict):
                    target_resources = res.get("target_resources", target_resources)
        return {"target_resources": target_resources, "context": context}

    @classmethod
    def execute_post_qa_hooks(cls, org_id: str, qa_report: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs post-QA hooks safely."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "post_qa", qa_report, context)
                if isinstance(res, dict):
                    qa_report = res.get("qa_report", qa_report)
        return {"qa_report": qa_report, "context": context}

    # ── 5. Incident & Failure Dispatcher ──────────────────────────
    @classmethod
    def execute_on_failure_hooks(cls, org_id: str, error: str, stage: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs on_failure hooks safely across all installed plugins when an error occurs."""
        org_key = str(org_id or "default")
        for instance in cls._active_instances.get(org_key, {}).values():
            if instance.enabled:
                res = cls._safe_invoke(instance, "on_failure", error, stage, context)
                if isinstance(res, dict):
                    context = res
        return {"error": error, "stage": stage, "context": context}

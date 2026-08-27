from typing import Dict, List, Any, Optional
from marketplace.catalog import AgentMarketplaceCatalog
from marketplace.plugin_sdk import BasePlugin

class PluginManager:
    """
    Marketplace & Plugin Lifecycle Manager.
    Manages per-organization installed plugins, custom hooks, and dynamic agent loading.
    """

    # In-memory registry of installed plugins per organization: {org_id: {plugin_id: PluginInstance}}
    _installed_plugins: Dict[str, Dict[str, Any]] = {}

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
            # Custom plugin
            meta = {
                "id": plugin_id,
                "name": plugin_id.replace("-", " ").title(),
                "version": "1.0.0",
                "custom": True
            }

        installed_record = {
            "id": plugin_id,
            "metadata": meta,
            "config": config or {},
            "enabled": True,
            "installed_at": "2026-08-22T00:00:00Z"
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
            return True
        return False

    @classmethod
    def list_installed(cls, org_id: str) -> List[Dict[str, Any]]:
        """Returns all installed plugins for an organization."""
        org_key = str(org_id or "default")
        return list(cls._installed_plugins.get(org_key, {}).values())

    @classmethod
    def execute_pre_plan_hooks(cls, org_id: str, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs pre-plan hooks across all enabled plugins."""
        org_key = str(org_id or "default")
        for p_id, p_data in cls._installed_plugins.get(org_key, {}).items():
            if p_data.get("enabled"):
                # Enrich context with plugin capabilities
                caps = p_data.get("metadata", {}).get("capabilities", [])
                if "active_capabilities" not in context:
                    context["active_capabilities"] = []
                context["active_capabilities"].extend(caps)
        return context

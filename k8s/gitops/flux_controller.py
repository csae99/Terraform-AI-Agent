"""
Flux CD Controller Integration for Terraform AI Operator.
Handles Flux GitRepository synchronization events, commit digests, and webhook receivers.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone


class FluxSyncEvent:
    """Represents a Flux CD synchronization event."""
    def __init__(self, repository: str, revision: str, commit_message: str):
        self.repository = repository
        self.revision = revision
        self.commit_message = commit_message
        self.received_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository": self.repository,
            "revision": self.revision,
            "commitMessage": self.commit_message,
            "receivedAt": self.received_at,
        }


class FluxController:
    """Manages Flux CD webhook callbacks and repository sync triggers."""

    def __init__(self):
        self.sync_history: List[FluxSyncEvent] = []

    def handle_webhook_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming Flux notification webhook payload.
        Expected format:
        {
            "involvedObject": {"kind": "GitRepository", "name": "infra-repo"},
            "message": "Fetched revision: main@sha1:e7b3c2...",
            "severity": "info"
        }
        """
        involved = payload.get("involvedObject", {})
        repo_name = involved.get("name", "unknown-repo")
        message = payload.get("message", "")
        severity = payload.get("severity", "info")

        # Extract revision hash if present
        revision = "unknown"
        if "revision:" in message:
            parts = message.split("revision:")
            if len(parts) > 1:
                revision = parts[1].strip()

        event = FluxSyncEvent(
            repository=repo_name,
            revision=revision,
            commit_message=message,
        )
        self.sync_history.append(event)

        return {
            "status": "Accepted",
            "repository": repo_name,
            "revision": revision,
            "severity": severity,
            "triggeredReconcile": True,
            "timestamp": event.received_at,
        }

    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent sync events."""
        return [e.to_dict() for e in self.sync_history[-limit:]]

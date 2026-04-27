import pytest
import os
from tools.project_tracker import ProjectTracker
from tools.deployment_tools import DeploymentTools
from agents import TerraformAgents

def test_project_tracker_db_save_load():
    """Verify metadata persistence in SQL DB."""
    test_slug = "test-unit-project"
    ProjectTracker.save(
        slug=test_slug,
        prompt="Unit test prompt",
        status="testing",
        provider="AWS"
    )
    
    loaded = ProjectTracker.load(test_slug)
    assert loaded is not None
    assert loaded["slug"] == test_slug
    assert loaded["status"] == "testing"
    assert loaded["provider"] == "AWS"

def test_drift_detection_logic_no_dir():
    """Verify drift tool handles missing directories gracefully."""
    result = DeploymentTools.detect_drift("non-existent-project")
    assert "Error" in result or "not found" in result.lower()

def test_agent_initialization():
    """Verify agents can be initialized with custom model config."""
    agents = TerraformAgents(model_name="openai/gpt-4o", api_key="sk-fake-key")
    architect = agents.architect()
    assert architect.role == "Cloud Architect"
    # Note: We don't call the LLM here to avoid using credits

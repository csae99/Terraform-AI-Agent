import os
import pytest
from tools.project.tracker import ProjectTracker
from orchestrator.retry_handler import RetryContext
from tools.deployment.testing_tools import TestingTools
from unittest.mock import patch, MagicMock

def test_decision_trace_tracking():
    """Verify that RetryContext decision trace behaves correctly."""
    ctx = RetryContext(max_rounds=3)
    ctx.record_decision("pipeline_started")
    ctx.record_decision("round_1_started")
    ctx.record_decision("terraform_validation_failed")
    ctx.record_decision("reflection_triggered")
    ctx.record_decision("search_triggered")
    ctx.record_decision("fix_applied")
    ctx.record_decision("pipeline_completed")
    
    assert ctx.decision_trace == [
        "pipeline_started",
        "round_1_started",
        "terraform_validation_failed",
        "reflection_triggered",
        "search_triggered",
        "fix_applied",
        "pipeline_completed"
    ]

def test_db_persistence_decision_trace():
    """Verify that ProjectTracker saves and loads decision_trace."""
    test_slug = "test-observability-project"
    trace = ["pipeline_started", "reflection_triggered", "success"]
    
    ProjectTracker.save(
        slug=test_slug,
        prompt="Testing observability",
        status="generated",
        decision_trace=trace
    )
    
    loaded = ProjectTracker.load(test_slug)
    assert loaded is not None
    assert loaded["decision_trace"] == trace
    
    # Clean up
    ProjectTracker.delete(test_slug)

def test_qa_testing_tools_sla():
    """Verify that SLA latency messages are injected in HTTP Endpoint check outputs."""
    tool_func = TestingTools.verify_http_endpoint.func
    
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = tool_func(url="http://localhost:8080", expected_status=200, timeout=5, sla_max_latency=0.001)
        assert "SLA" in result
        assert "✅" in result
        
        # Test transient error retry with mock
        # Make the first 2 responses 503, and the third 200
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        
        mock_get.side_effect = [mock_response_503, mock_response_503, mock_response]
        
        with patch("time.sleep") as mock_sleep:
            result_retry = tool_func(url="http://localhost:8080", expected_status=200, timeout=5, sla_max_latency=2.0)
            assert mock_sleep.call_count == 2
            assert "✅" in result_retry

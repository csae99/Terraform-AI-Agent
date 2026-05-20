import pytest
from fastapi.testclient import TestClient
from app.dashboard import app, get_current_user

class MockUser:
    id = 1
    username = "testuser"

@pytest.fixture
def client():
    # Override authentication for testing
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_api_stats(client):
    """Verify global stats endpoint returns expected structure."""
    rv = client.get('/api/stats')
    assert rv.status_code == 200
    data = rv.json()
    assert 'total_projects' in data
    assert 'total_monthly_cost' in data

def test_api_projects_list(client):
    """Verify projects list endpoint."""
    rv = client.get('/api/projects')
    assert rv.status_code == 200
    data = rv.json()
    assert isinstance(data, list)

def test_api_invalid_project(client):
    """Verify 404 for non-existent project."""
    rv = client.get('/api/projects/does-not-exist')
    assert rv.status_code == 404

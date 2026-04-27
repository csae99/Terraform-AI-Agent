import pytest
from dashboard import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_stats(client):
    """Verify global stats endpoint returns expected structure."""
    rv = client.get('/api/stats')
    data = json.loads(rv.data)
    assert 'total_projects' in data
    assert 'total_monthly_cost' in data
    assert rv.status_code == 200

def test_api_projects_list(client):
    """Verify projects list endpoint."""
    rv = client.get('/api/projects')
    data = json.loads(rv.data)
    assert isinstance(data, list)
    assert rv.status_code == 200

def test_api_invalid_project(client):
    """Verify 404 for non-existent project."""
    rv = client.get('/api/projects/does-not-exist')
    assert rv.status_code == 404

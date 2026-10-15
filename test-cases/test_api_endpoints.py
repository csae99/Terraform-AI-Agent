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

def test_gitops_push_lifecycle(client):
    """Verify post-provisioning GitOps push and PR creation workflow."""
    import os
    import shutil
    from tools.project.tracker import ProjectTracker

    test_slug = "test-gitops-lifecycle"
    test_dir = os.path.join("output", test_slug)
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, "main.tf"), "w", encoding="utf-8") as f:
        f.write('# test terraform\nresource "local_file" "sample" { content = "ok" filename = "sample.txt" }\n')

    try:
        ProjectTracker.save(slug=test_slug, prompt="Test gitops push prompt", status="generated", owner_id=1)

        # 1. Missing repo_url returns 400
        res_bad = client.post(f"/api/projects/{test_slug}/gitops/push", json={})
        assert res_bad.status_code == 400

        # 2. Valid push (simulated PR)
        res_good = client.post(f"/api/projects/{test_slug}/gitops/push", json={
            "repo_url": "https://github.com/my-test-org/infra-repo.git",
            "target_branch": "main"
        })
        assert res_good.status_code == 200
        data = res_good.json()
        assert data["success"] is True
        assert "pr_url" in data
        assert data["pr_number"] is not None
        assert data["approval_status"] == "pending"

        # 3. Verify GET returns updated gitops metadata
        res_get = client.get(f"/api/projects/{test_slug}/gitops")
        assert res_get.status_code == 200
        get_data = res_get.json()
        assert get_data["pr_url"] == data["pr_url"]
        assert get_data["pr_number"] == data["pr_number"]
        assert get_data["approval_status"] == "pending"
    finally:
        ProjectTracker.delete(test_slug)
        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


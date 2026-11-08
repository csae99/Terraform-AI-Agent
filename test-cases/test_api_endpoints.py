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

        # 2. Valid push (mocked git operations to isolate test from host git repository)
        from unittest.mock import patch
        with patch("tools.gitops.gitops_tools.GitOpsTools.create_feature_branch", return_value={"success": True, "branch_name": f"ai/{test_slug}-mock"}), \
             patch("tools.gitops.gitops_tools.GitOpsTools.commit_files", return_value={"success": True, "commit_hash": "mock123"}), \
             patch("tools.gitops.gitops_tools.GitOpsTools.push_branch", return_value={"success": True, "branch_name": f"ai/{test_slug}-mock", "repo_url": "https://github.com/my-test-org/infra-repo.git"}):
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

def test_live_deploy_lifecycle(client):
    """Verify on-demand live deploy and plan workflow for existing workspaces."""
    import os
    import shutil
    from unittest.mock import patch
    from tools.project.tracker import ProjectTracker, KillSwitchManager

    test_slug = "test-live-deploy-lifecycle"
    test_dir = os.path.join("output", test_slug)
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, "main.tf"), "w", encoding="utf-8") as f:
        f.write('# AWS Provider Test\nprovider "aws" { region = "us-east-1" }\nresource "aws_s3_bucket" "b" { bucket = "sample" }\n')

    try:
        ProjectTracker.save(slug=test_slug, prompt="Test live deploy prompt", status="generated", owner_id=1)

        # 1. Non-existent slug returns 404
        res_404 = client.post("/api/projects/non-existent-slug-xyz/deploy", json={"action": "plan"})
        assert res_404.status_code == 404

        # 2. Invalid action returns 400
        res_bad = client.post(f"/api/projects/{test_slug}/deploy", json={"action": "invalid_action"})
        assert res_bad.status_code == 400

        # 3. Emergency Kill Switch blocks deployment
        with patch("tools.project.tracker.KillSwitchManager.is_active", return_value=True):
            res_blocked = client.post(f"/api/projects/{test_slug}/deploy", json={"action": "apply"})
            assert res_blocked.status_code == 403

        # 4. Check initial deployment-status endpoint
        status_res = client.get(f"/api/projects/{test_slug}/deployment-status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["is_deployed"] is False
        assert status_data["status"] == "generated"
        assert status_data["detected_provider"] == "aws"

        # 5. Run Plan (mocked engine)
        with patch("tools.engine.base.IaCEngine.plan", return_value={"success": True, "exit_code": 0, "stdout": "Plan: 1 to add", "stderr": ""}):
            plan_res = client.post(f"/api/projects/{test_slug}/deploy", json={"action": "plan"})
            assert plan_res.status_code == 200
            plan_data = plan_res.json()
            assert plan_data["success"] is True
            assert plan_data["action"] == "plan"
            assert plan_data["status"] == "generated"

        # 6. Run Apply (mocked engine)
        with patch("tools.engine.base.IaCEngine.apply", return_value={"success": True, "exit_code": 0, "stdout": "Apply complete! 1 added.", "stderr": ""}):
            apply_res = client.post(f"/api/projects/{test_slug}/deploy", json={
                "action": "apply",
                "credentials": {"AWS_ACCESS_KEY_ID": "AKIA_MOCK", "AWS_SECRET_ACCESS_KEY": "SECRET_MOCK"}
            })
            assert apply_res.status_code == 200
            apply_data = apply_res.json()
            assert apply_data["success"] is True
            assert apply_data["action"] == "apply"
            assert apply_data["status"] == "deployed"
            assert apply_data["deployed_at"] is not None

        # 7. Check updated deployment status
        status_res_after = client.get(f"/api/projects/{test_slug}/deployment-status")
        assert status_res_after.status_code == 200
        assert status_res_after.json()["is_deployed"] is True
        assert status_res_after.json()["status"] == "deployed"

        # 8. Destroy Infrastructure
        with patch("tools.engine.base.IaCEngine.destroy", return_value={"success": True, "exit_code": 0, "stdout": "Destroy complete!", "stderr": ""}):
            destroy_res = client.post(f"/api/projects/{test_slug}/destroy", json={})
            assert destroy_res.status_code == 200
            destroy_data = destroy_res.json()
            assert destroy_data["success"] is True
            assert destroy_data["status"] == "destroyed"
    finally:
        ProjectTracker.delete(test_slug)
        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


def test_workspace_evolution_lifecycle(client):
    """Verify workspace evolution workflow: pre-snapshot archiving, RBAC, kill switches, and diffing."""
    import os
    import shutil
    from unittest.mock import patch
    from tools.project.tracker import ProjectTracker

    test_slug = "test-evolution-project"
    test_dir = os.path.join("output", test_slug)
    os.makedirs(test_dir, exist_ok=True)
    initial_hcl = '# Baseline Terraform Code\nresource "aws_s3_bucket" "b1" {\n  bucket = "test-evo-bucket"\n}\n'
    with open(os.path.join(test_dir, "main.tf"), "w", encoding="utf-8") as f:
        f.write(initial_hcl)

    try:
        ProjectTracker.save(slug=test_slug, prompt="Initial bucket", status="generated", owner_id=1)

        # 1. 404 for non-existent workspace
        res_404 = client.post("/api/projects/non-existent-workspace-xyz/evolve", json={"prompt": "Add KMS key"})
        assert res_404.status_code == 404

        # 2. 400 for empty prompt
        res_400 = client.post(f"/api/projects/{test_slug}/evolve", json={"prompt": "   "})
        assert res_400.status_code == 400

        # 3. 403 on emergency kill switch (generation_disabled)
        with patch("tools.project.tracker.KillSwitchManager.is_active", side_effect=lambda name: name == "generation_disabled"):
            res_kill = client.post(f"/api/projects/{test_slug}/evolve", json={"prompt": "Add KMS key"})
            assert res_kill.status_code == 403

        # 4. Valid evolution invocation (mocking background task execution)
        with patch("app.dashboard.run_agent_workflow") as mock_workflow:
            res_evolve = client.post(f"/api/projects/{test_slug}/evolve", json={
                "prompt": "Add customer-managed KMS key and enable bucket encryption",
                "apply": False,
                "engine": "terraform"
            })
            assert res_evolve.status_code == 200
            data = res_evolve.json()
            assert data["status"] == "started"
            assert data["slug"] == test_slug
            pre_snap = data["pre_snapshot"]
            assert pre_snap is not None
            assert test_slug in pre_snap

        # 5. Verify pre-evolution snapshot is archived on disk
        snap_path = os.path.join(test_dir, "backups", pre_snap, "main.tf")
        assert os.path.exists(snap_path)
        with open(snap_path, "r", encoding="utf-8") as sf:
            assert sf.read() == initial_hcl

        # 6. Verify snapshot endpoint lists the newly created baseline snapshot
        snap_res = client.get(f"/api/projects/{test_slug}/snapshots")
        assert snap_res.status_code == 200
        snap_list = snap_res.json()
        assert any(s["id"] == pre_snap for s in snap_list)

        # 7. Simulate agent updating the main.tf code with the evolved changes
        evolved_hcl = (
            '# Baseline Terraform Code\n'
            'resource "aws_s3_bucket" "b1" {\n'
            '  bucket = "test-evo-bucket"\n'
            '}\n'
            '\n'
            'resource "aws_kms_key" "mykey" {\n'
            '  description = "Encryption Key"\n'
            '}\n'
        )
        with open(os.path.join(test_dir, "main.tf"), "w", encoding="utf-8") as f:
            f.write(evolved_hcl)

        # 8. Verify diff endpoint returns the unified diff highlighting the additions
        diff_res = client.get(f"/api/projects/{test_slug}/diff/{pre_snap}")
        assert diff_res.status_code == 200
        diff_data = diff_res.json()
        assert "+resource \"aws_kms_key\" \"mykey\"" in diff_data["diff"]

        # 9. Verify /api/projects/{slug}/code excludes files from backups/
        code_res = client.get(f"/api/projects/{test_slug}/code")
        assert code_res.status_code == 200
        code_files = code_res.json()
        assert "main.tf" in code_files
        assert not any("backups" in k for k in code_files.keys())
    finally:
        ProjectTracker.delete(test_slug)
        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)

def test_api_runs_status(client):
    """Verify /api/runs/status endpoint returns expected structure."""
    rv = client.get('/api/runs/status')
    assert rv.status_code == 200
    data = rv.json()
    assert 'running' in data
    assert 'status' in data
    assert 'logs' in data

def test_delete_and_normalize_provider_files():
    """Verify safe file deletion and duplicate provider file normalization."""
    import os
    import shutil
    from tools.terraform.terraform_tools import TerraformTools

    test_slug = "test-normalize-prov"
    test_dir = os.path.join("output", test_slug)
    os.makedirs(test_dir, exist_ok=True)

    try:
        providers_path = os.path.join(test_dir, "providers.tf")
        versions_path = os.path.join(test_dir, "versions.tf")
        dummy_file = os.path.join(test_dir, "dummy.tf")

        with open(providers_path, "w") as f: f.write('# providers.tf\n')
        with open(versions_path, "w") as f: f.write('# versions.tf\n')
        with open(dummy_file, "w") as f: f.write('# dummy\n')

        # 1. Normalizer should remove versions.tf and keep providers.tf
        actions = TerraformTools._normalize_workspace_provider_files(test_slug)
        assert len(actions) == 1
        assert os.path.exists(providers_path)
        assert not os.path.exists(versions_path)

        # 2. Delete tool should safely delete dummy.tf
        del_msg = TerraformTools._delete_terraform_file(test_slug, "dummy.tf")
        assert "Successfully deleted" in del_msg
        assert not os.path.exists(dummy_file)

        # 3. Path traversal security check
        traversal_msg = TerraformTools._delete_terraform_file(test_slug, "../../app/dashboard.py")
        assert "Security violation" in traversal_msg
    finally:
        if os.path.isdir(test_dir):
            shutil.rmtree(test_dir, ignore_errors=True)


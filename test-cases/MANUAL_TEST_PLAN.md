# 🛠️ Terraform AI Agent: Manual E2E Test Plan

This document outlines the steps to manually verify the entire platform lifecycle.

## 1. AI Infrastructure Generation
- **Input**: "Create an AWS S3 bucket named `test-audit-bucket` with versioning enabled and a lifecycle rule to transition to Glacier after 30 days."
- **Budget**: $50
- **Expectation**: 
    - [ ] Architect generates a Mermaid diagram.
    - [ ] Specialist generates valid `main.tf`.
    - [ ] Security Specialist finds no critical issues (or fixes them).
    - [ ] Financial Analyst estimates cost < $50.

## 2. Visual Topology & Evolution
- **Action**: Open the project in the Dashboard.
- **Expectation**:
    - [ ] **Visual Topology** tab renders a diagram of the S3 bucket and lifecycle rule.
    - [ ] **Evolution History** shows at least one snapshot (Round 1).

## 3. Multi-Cloud Deployment (Live)
- **Action**: Provide AWS Credentials in the UI and toggle "Live Deploy".
- **Expectation**:
    - [ ] Live Console shows `terraform init` and `terraform apply`.
    - [ ] Status badge changes to `deployed`.

## 4. Drift Detection (The "Snooper" Test)
- **Action**:
    1. Manually go to the AWS Console and change a tag on the bucket.
    2. Click **🔍 Scan for Drift** in the dashboard.
* **Expectation**:
    - [ ] Dashboard alert shows: `⚠️ DRIFT DETECTED`.
    - [ ] Status badge changes to `drifted`.

## 5. Persistence Recovery
- **Action**: Run `docker-compose restart`.
- **Expectation**:
    - [ ] Refresh dashboard. All projects and logs must still be present (retrieved from PostgreSQL/SQLite).

## 6. Multi-Tenant Organization Workspaces
- **Action**:
    1. Click the **+ New Org** button in the header.
    2. Enter an organization name (e.g. `DevOps Engineering`) and submit.
- **Expectation**:
    - [ ] Organization is created and user is assigned the `OWNER` role.
    - [ ] Workspace selector automatically switches to `🏢 DevOps Engineering (OWNER)`.
    - [ ] "Team Members" button appears next to the workspace selector.
    - [ ] Projects list displays 0 projects (scoped to new org).

## 7. Team Invitation & RBAC Enforcement
- **Action**:
    1. Click **👥 Team Members** in the org workspace context.
    2. Invite another registered user with role `Viewer`.
    3. Log in as the invited `Viewer` user and switch to the organization workspace.
    4. Attempt to generate new infrastructure.
- **Expectation**:
    - [ ] Viewer can view existing org projects and stats.
    - [ ] Generation request is blocked by server-side RBAC with a 403 Forbidden alert.
    - [ ] Switching back to `👤 Personal Workspace` restores personal projects and full generation rights.


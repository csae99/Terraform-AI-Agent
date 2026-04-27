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
    - [ ] Refresh dashboard. All projects and logs must still be present (retrieved from PostgreSQL).

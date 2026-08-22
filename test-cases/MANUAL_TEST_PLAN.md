# 🛠️ Autonomous Infrastructure Platform: Complete Manual E2E Test Plan (Phases 1 – 13)

This document provides a comprehensive, step-by-step testing roadmap to verify every capability of the **Autonomous Infrastructure Platform** from **Phase 1 through Phase 13**.

> [!TIP]
> **Optimized for Google Gemini Free Tier**: The test prompts and configurations below use lightweight, cost-effective infrastructure prompts designed to execute smoothly within standard Gemini API rate limits (`gemini-2.0-flash`).

---

## ⚙️ Environment Setup & Prerequisites

Before beginning tests, ensure your local environment is configured:

1. **Verify your `.env` file**:
   ```env
   # Active Model (Gemini Free Tier recommended)
   DEFAULT_MODEL=gemini/gemini-2.0-flash
   GEMINI_API_KEY=your_gemini_api_key_here

   # Default IaC Engine ('terraform' or 'opentofu')
   DEFAULT_IAC_ENGINE=terraform

   # Local Emulation (Floci) & Database
   TEST_LOCAL=true
   DATABASE_URL=sqlite:///terraform_agent.db
   REDIS_URL=redis://localhost:6379/0

   # Payment Gateways (Simulation Mode)
   DEFAULT_PAYMENT_GATEWAY=razorpay
   RAZORPAY_KEY_ID=rzp_test_mock
   RAZORPAY_KEY_SECRET=mock_secret
   STRIPE_PUBLISHABLE_KEY=pk_test_mock
   STRIPE_SECRET_KEY=sk_test_mock
   ```

2. **Launch the Dashboard**:
   ```powershell
   # In terminal:
   python app/dashboard.py
   # Open browser at: http://localhost:5000
   ```

3. **Default Test Accounts**:
   - Register or login with: `username: testuser1`, `password: test1234`

---

## 📋 Comprehensive Test Matrix

---

### 1. 🏗️ Core Infrastructure Generation & Code Viewer (Phases 1 & 2)
- **Objective**: Verify that the multi-agent system architects, codes, audits, and estimates costs for a standard infrastructure requirement without hitting rate limits.
- **Action**:
  1. Open the **Build** tab on `http://localhost:5000`.
  2. In **Infrastructure Requirement**, enter:
     ```text
     Create an AWS S3 bucket named test-vault-storage with versioning enabled and a lifecycle rule to transition objects to Glacier after 30 days.
     ```
  3. Set **Budget (USD)** to `50`.
  4. Ensure **Live Deploy** is unchecked. Keep **New Workspace** checked.
  5. Click **Generate**.
- **Expectation**:
  - [ ] Agent Live Stream modal opens and logs the execution sequence (Architect $\rightarrow$ Developer $\rightarrow$ Security $\rightarrow$ FinOps).
  - [ ] Notification toast displays *"Generation Complete!"*.
  - [ ] Project modal automatically opens showing the **Terraform Code** tab with syntax-highlighted `main.tf`, `variables.tf`, and `outputs.tf`.
  - [ ] The **Visual Topology** tab displays an interactive Mermaid diagram with the S3 bucket node connected to the Glacier transition rule.
  - [ ] The **FinOps Report** tab shows projected cost compliant with the $50 budget (`STATUS: WITHIN BUDGET`).

---

### 2. 🗺️ Visual Topology, File Explorer & Evolution History (Phase 2 & 3)
- **Objective**: Verify project navigation, multi-file inspection, and version-controlled snapshot diffs.
- **Action**:
  1. In the open project modal, switch between the code file tabs (`main.tf`, `modules/...`).
  2. Click the **🕒 Evolution History** tab.
  3. Click **Round 1 (Initial)** and compare changes in the diff viewer.
- **Expectation**:
  - [ ] Code viewer switches files instantly without rendering lag.
  - [ ] Evolution history renders green additions (`+`) and red deletions (`-`) representing changes across agent rounds.

---

### 3. 🔍 Cloud Drift Detection ("The Snooper Test") (Phase 4)
- **Objective**: Verify that the platform can detect divergence between the live infrastructure state and the declarative Terraform definition.
- **Action**:
  1. Open any generated workspace in the dashboard.
  2. In the project header, click **🔍 Scan for Drift**.
- **Expectation**:
  - [ ] The drift status badge shows `⏳ Scanning...`.
  - [ ] Drift scanner completes and updates status badge to `in_sync` (or `drifted` with detailed attribute diffs).

---

### 4. 🏢 Multi-Tenant Organizations & RBAC Permissions (Phase 10)
- **Objective**: Verify multi-tenant workspace isolation and role-based access control (`Owner`, `Admin`, `Member`, `Viewer`).
- **Action**:
  1. In the header dropdown, click **+ New Org**.
  2. Enter organization name: `Acme Cloud Team` and click **Create Org**.
  3. Notice header switches to `🏢 Acme Cloud Team (OWNER)`.
  4. Click the **👥 Team Members** modal (accessible via header).
  5. Invite a second registered user (e.g. `testuser2`) with the **Viewer** role.
  6. In an Incognito window, log in as `testuser2` and switch to `Acme Cloud Team`.
  7. As `testuser2` (Viewer), attempt to click **Generate** on the Build tab.
- **Expectation**:
  - [ ] Organization is created and isolated from personal workspaces.
  - [ ] `testuser2` (Viewer) can view projects and statistics but is **blocked from generating or deleting infrastructure** with a `403 Forbidden` alert.
  - [ ] Switching back to `👤 Personal Workspace` restores personal ownership and full permissions.

---

### 5. 🔀 GitOps Pull Request Automation & Approval Gate (Phase 11)
- **Objective**: Test automated Git branch synthesis, Pull Request generation, and Organization Owner approval gates.
- **Action**:
  1. On the **Build** tab, check **GitOps Mode**.
  2. Expand the **🔀 GitOps & Pull Request Automation** section.
  3. Provide a test Git repo URL (e.g. `https://github.com/my-org/cloud-infra.git`), branch `main`, and your GitHub PAT (or leave default for simulation).
  4. Enter prompt: `Create a secure private subnet with an AWS security group for web traffic`.
  5. Click **Generate**.
  6. Open the created project and navigate to the **🔀 GitOps & PR** tab.
  7. As a standard **Member**, verify that clicking **Approve PR** is disabled or rejected.
  8. As the **Organization Owner**, click **Approve PR**, then click **Merge & Deploy**.
- **Expectation**:
  - [ ] Agent generates isolated branch `ai/{slug}-{timestamp}` with staged `.tf` files.
  - [ ] Pull Request status updates to `⏳ Pending Approval`.
  - [ ] Organization Owner approval transitions status to `✅ Approved` with approver's name.
  - [ ] Clicking **Merge & Deploy** marks the release as `🚀 Merged`.

---

### 6. 📜 Enterprise Audit Trail & SOC2 Log Export (Phase 11 & 12)
- **Objective**: Verify immutable audit logging and compliance export.
- **Action**:
  1. Click the **Audit Trail** tab in the main top navigation.
  2. Review the chronological events table.
  3. Click **Export JSON** and **Export CSV**.
- **Expectation**:
  - [ ] Audit trail table records all user actions (`gitops_pr_created`, `gitops_pr_approved`, `org_created`, `member_added`) with exact timestamps and user tags.
  - [ ] `soc2_compliance_package.json` downloads with complete metadata, workspace inventory, and signed audit records.
  - [ ] `soc2_compliance_audit_trail.csv` downloads as a valid CSV spreadsheet.

---

### 7. 🟣 Dual IaC Engine Selection (Terraform & OpenTofu) (Phase 11.5)
- **Objective**: Verify that the platform seamlessly executes and tracks infrastructure targeting both HashiCorp Terraform and Linux Foundation OpenTofu.
- **Action**:
  1. On the **Build** tab, locate the **IaC Engine** selector.
  2. Select **🧅 OpenTofu**.
  3. Enter prompt: `Create a private S3 bucket with server-side encryption`.
  4. Click **Generate**.
- **Expectation**:
  - [ ] Project builds successfully targeting OpenTofu.
  - [ ] Project header displays the purple **`🧅 OpenTofu`** badge.
  - [ ] Fallback mechanism smoothly handles environments without `tofu` installed by falling back to `terraform` with informative logging.

---

### 8. 📊 Executive Observability & Prometheus Metrics (Phase 12)
- **Objective**: Verify OpenTelemetry tracing, Prometheus exposition, and executive analytics.
- **Action**:
  1. Click the **Analytics & Observability** tab in the top navigation.
  2. Inspect the KPI cards: **Success Rate**, **Financial Savings**, **Monthly Infra Spend**, **Self-Healing Rounds**.
  3. Review the **Failure Taxonomy Breakdown** chart.
  4. Click the **Prometheus Metrics** link (opens `/api/observability/metrics?format=prometheus`).
- **Expectation**:
  - [ ] KPIs compute accurate real-time values from the database.
  - [ ] Failure taxonomy categorizes errors into clear buckets (`IAM`, `Naming Conflict`, `Syntax`).
  - [ ] Prometheus metrics page displays raw text metrics (`terraform_agent_runs_total`, `terraform_agent_tokens_total`, etc.).

---

### 9. 💳 Usage Metering & Dual Payment Gateways (Razorpay & Stripe) (Phase 12)
- **Objective**: Verify 3-way cost attribution metering and subscription upgrades using Razorpay or Stripe.
- **Action**:
  1. Click the **Billing & Plans** tab.
  2. Review the **Monthly Execution Quota** progress bar (e.g. `0 / 5 Runs Used` on Free tier).
  3. Review the **3-Way Cost Attribution** cards:
     - *Total LLM Tokens* (Prompt + Completion token cost)
     - *Worker Compute Seconds* (Platform compute fee)
     - *Projected Cloud Spend* (Infracost estimate)
  4. Click **Upgrade Plan**.
  5. Toggle between **Razorpay (UPI / Cards / NetBanking)** and **Stripe (Global Cards)**.
  6. Click **Upgrade to Pro** ($29/mo).
- **Expectation**:
  - [ ] Dual gateway buttons toggle active styles.
  - [ ] Upgrade request succeeds and updates subscription tier to **PRO DEVELOPER** (100 runs/month quota).
  - [ ] Quota bar recalculates percentage against the new tier limit.

---

### 10. 🧠 pgvector Knowledge Layer & Semantic Pattern Matching (Phase 12 & 13)
- **Objective**: Verify database-backed pattern memory and semantic vector search (RAG).
- **Action**:
  1. Open a terminal or test script to trigger a semantic failure query:
     ```python
     # Via Python or curl
     import requests
     res = requests.get("http://localhost:5000/api/knowledge/patterns/semantic?error_query=AWS refused bucket creation because name is taken")
     print(res.json())
     ```
  2. Query documentation search:
     ```python
     res = requests.get("http://localhost:5000/api/knowledge/search?q=opentofu state encryption")
     print(res.json())
     ```
- **Expectation**:
  - [ ] Semantic search returns `BucketAlreadyExists` pattern even though the error phrasing differed from exact substring.
  - [ ] Documentation search returns relevant OpenTofu and AWS S3 encryption runbooks.

---

### 11. 🛡️ Policy-as-Code & OPA Rego Evaluation (Phase 13)
- **Objective**: Verify Open Policy Agent (OPA) compliance packs (SOC2, HIPAA, PCI-DSS, CIS Benchmarks) and Organization Guardrails.
- **Action**:
  1. Test non-compliant HCL against SOC2:
     ```bash
     curl -X POST http://localhost:5000/api/policy/evaluate \
       -H "Content-Type: application/json" \
       -d "{\"hcl_code\": \"resource \\\"aws_s3_bucket\\\" \\\"data\\\" {}\", \"pack\": \"soc2\"}"
     ```
  2. Test compliant HCL against SOC2:
     ```bash
     curl -X POST http://localhost:5000/api/policy/evaluate \
       -H "Content-Type: application/json" \
       -d "{\"hcl_code\": \"resource \\\"aws_s3_bucket\\\" \\\"data\\\" { block_public_acls = true encrypted = true } resource \\\"aws_s3_bucket_public_access_block\\\" \\\"data\\\" { bucket = \\\"data\\\" block_public_acls = true block_public_policy = true } resource \\\"aws_s3_bucket_server_side_encryption_configuration\\\" \\\"data\\\" { bucket = \\\"data\\\" }\", \"pack\": \"soc2\"}"
     ```
  3. Test Organization Guardrails (Region & Budget whitelist):
     ```bash
     curl -X POST http://localhost:5000/api/policy/guardrails \
       -H "Content-Type: application/json" \
       -d "{\"hcl_code\": \"provider \\\"aws\\\" { region = \\\"ap-south-1\\\" }\", \"budget\": 250, \"allowed_regions\": [\"us-east-1\", \"us-west-2\"], \"max_budget_cap\": 100}"
     ```
- **Expectation**:
  - [ ] Non-compliant HCL returns `allow: false` with specific violation descriptions (missing public access block / encryption).
  - [ ] Compliant HCL returns `allow: true` and `compliance_score_percent: 100.0`.
  - [ ] Guardrails correctly flags unauthorized region (`ap-south-1`) and budget exceeding cap ($250 > $100).

---

### 12. 🔐 Enterprise SSO & Identity Federation (Phase 13)
- **Objective**: Verify OAuth2/OIDC discovery and user auto-provisioning for Microsoft Entra ID, Okta, Google Workspace, and Auth0.
- **Action**:
  1. Query supported SSO providers:
     ```bash
     curl http://localhost:5000/api/auth/sso/providers
     ```
  2. Request SSO redirect URL for Okta:
     ```bash
     curl http://localhost:5000/api/auth/sso/login/okta
     ```
  3. Simulate SSO callback & auto-provisioning:
     ```bash
     curl -X POST http://localhost:5000/api/auth/sso/callback/okta \
       -H "Content-Type: application/json" \
       -d "{\"code\": \"mock_code_123\", \"simulated_user\": {\"email\": \"alex.cloud@enterprise.com\", \"name\": \"Alex Cloud\"}}"
     ```
- **Expectation**:
  - [ ] Provider list returns `google`, `azure_ad`, `okta`, and `auth0`.
  - [ ] SSO callback auto-provisions `alex.cloud` in the database, returns active session payload, and sets the secure authentication cookie.

---

### 13. 🤖 Multi-Agent Consensus & Debate Engine (Phase 13)
- **Objective**: Verify multi-agent competitive architectural debate between Developer Agent A (Enterprise Scale), Developer Agent B (Lean Cost), and the Reviewer.
- **Action**:
  1. Execute an architectural debate request:
     ```bash
     curl -X POST http://localhost:5000/api/consensus/debate \
       -H "Content-Type: application/json" \
       -d "{\"prompt\": \"Design high-throughput payment transaction queue\", \"budget\": 100, \"provider\": \"AWS\"}"
     ```
- **Expectation**:
  - [ ] Response contains proposals from Developer A (Scale & HA) and Developer B (Lean Serverless).
  - [ ] 4-dimensional weighted consensus matrix scores both proposals (Security 35%, Cost 25%, Reliability 25%, Simplicity 15%).
  - [ ] Reviewer outputs decision summary ratifying the winning blueprint with composite score.

---

### 14. ☁️ Multi-Cloud Architecture Optimization (Phase 13)
- **Objective**: Verify automated cross-cloud comparison between AWS, Azure, and GCP.
- **Action**:
  1. Compare cloud providers for an application stack:
     ```bash
     curl -X POST http://localhost:5000/api/cloud-optimizer/compare \
       -H "Content-Type: application/json" \
       -d "{\"prompt\": \"Deploy containerized web app with PostgreSQL database and object storage\", \"budget\": 100}"
     ```
- **Expectation**:
  - [ ] Returns side-by-side cost projections, primary services, and HA SLAs for AWS, Azure, and GCP.
  - [ ] Selects and explains the recommended cloud provider based on pricing and SLA guarantees.

---

### 15. 📈 AI Operations Center (AIOps) & Model Routing (Phase 13)
- **Objective**: Verify real-time AIOps telemetry, active governance alerts, and task-complexity model routing.
- **Action**:
  1. Query AIOps system health: `curl http://localhost:5000/api/aiops/status`
  2. Query active governance alerts: `curl http://localhost:5000/api/aiops/alerts`
  3. Test model routing for a simple task:
     ```bash
     curl -X POST http://localhost:5000/api/aiops/route-model \
       -H "Content-Type: application/json" \
       -d "{\"prompt\": \"Create simple S3 bucket\", \"task_type\": \"general\"}"
     ```
  4. Test model routing for a complex task:
     ```bash
     curl -X POST http://localhost:5000/api/aiops/route-model \
       -H "Content-Type: application/json" \
       -d "{\"prompt\": \"Design HIPAA compliant Multi-AZ Kubernetes cluster with Vault KMS encryption\", \"task_type\": \"debate\"}"
     ```
- **Expectation**:
  - [ ] `AIOps status` reports health (`OPTIMAL`), workspace counts, self-healed runs, and pattern bank metrics.
  - [ ] Simple task routes to `fast_lean` tier (`gemini-2.0-flash`).
  - [ ] Security-critical / debate task routes to `frontier_expert` tier (`gpt-4o` / `gemini-1.5-pro`).

---

## ⚡ Quick Automated Sanity Script

To run all backend unit and integration tests at once:
```powershell
.\venv313\Scripts\python.exe scratch/test_phase13.py
.\venv313\Scripts\python.exe scratch/test_vector_knowledge.py
.\venv313\Scripts\python.exe scratch/test_observability.py
.\venv313\Scripts\python.exe scratch/test_billing.py
```
*Expected Result: All test suites output `🎉 ALL TESTS PASSED SUCCESSFULLY!` with 0 errors.*

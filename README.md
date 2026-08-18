# 🤖 Universal Terraform AI Agent (Phase 11: Enterprise GitOps & PR Automation)

A powerful, interactive, and modular AI system designed to generate enterprise-grade Terraform infrastructure. Built to be **Universal**, it can be powered by cloud LLMs (Gemini, Groq, Mistral, OpenAI, ZenMux) or run entirely locally via **Ollama**. Features **GitHub & GitLab Pull Request Automation**, **Enterprise Team Approval Gates**, **Audit Trails**, and **Multi-Organization Workspaces** with Role-Based Access Control (RBAC).

---

- **IaC Engine Abstraction Layer & OpenTofu Integration** *(Phase 12)*: Universal runtime abstraction layer supporting both **HashiCorp Terraform** (`terraform`) and **Linux Foundation OpenTofu** (`tofu`). Execute formatting, validation, planning, application, drift detection, and state tracking seamlessly across either engine with automatic discovery and intelligent fallback.
- **Enterprise GitOps & PR Automation** *(Phase 11)*: Automated feature branch creation (`ai/{slug}-{timestamp}`), deterministic file staging, commit generation, and GitHub/GitLab Pull Request synthesis with rich Markdown templates containing visual Mermaid diagrams, Infracost breakdowns, and Checkov security reports.
- **Team Approval Gates & Audit Trails** *(Phase 11)*: Multi-tier approval workflow where Pull Requests require sign-off by Organization Owners or Admins prior to live cloud mutation. Comprehensive immutable audit logging (`AuditTracker`) captures every event (`gitops_pr_created`, `gitops_pr_approved`, `gitops_pr_merged_and_deployed`) across teams.
- **Multi-Tenant Organizations & RBAC** *(Phase 10)*: GitHub-style **multi-organization workspaces** with team collaboration. Create organizations, invite members by username, assign roles (Owner, Admin, Member, Viewer), and seamlessly switch between Personal and Organization contexts. Viewer role is restricted from generating/destroying infrastructure.
- **Multi-Agent Orchestration**: Powered by **CrewAI**, utilizing 7 specialized agents (Architect, Developer, Security Reviewer, FinOps Specialist, Deployment Planner, QA Testing Agent, and GitOps Coordinator) for a robust production pipeline.
- **Central Pipeline Orchestrator**: A dedicated `orchestrator/` module provides a single authoritative entry-point (`run_full_pipeline`) for both the CLI and Web Dashboard, with built-in self-healing retry logic.
- **Asynchronous Job Queue**: Powered by **Celery** and **Redis** to run heavy Terraform generation, deployment, and testing tasks concurrently in the background without blocking the web gateway.
- **Local AWS Emulation**: Integrated **Floci** (a local, high-speed AWS emulator) to test deploy mock resources (S3, EC2, RDS, Lambda, DynamoDB, SQS) completely free of charge.
- **Continuous QA Testing Agent**: A dedicated agent that runs post-apply behavior verification tests (HTTP checks, S3 read/write validations, AWS resource status audits) against emulated or real environments.
- **Failure Pattern Memory & Self-Learning**: When Terraform errors are successfully resolved via retries, the system triggers an LLM self-learning loop to automatically extract the root cause and update `failure_patterns.json` dynamically, continuously expanding its own knowledge bank.
- **Universal LLM Support**: Powered by **LiteLLM**, allowing you to swap between 100+ providers (Gemini, Groq, Mistral, OpenAI, ZenMux) via a single `.env` setting or the Web UI.
- **Web Dashboard**: Full-featured FastAPI dashboard with user authentication, organization management, project isolation, live agent log streaming, visual topology (Mermaid.js), FinOps reports, and Enterprise Audit Trail view.
- **Modular by Default**: Automatically generates organized "Root + Submodules" structures under the `modules/` directory (e.g. `modules/networking/`, `modules/aks/`) for any multi-resource projects, guaranteeing high-quality, reusable Terraform code.
- **AI Self-Healing & Web-Search**: The system automatically identifies security vulnerabilities and live deployment errors, initiating autonomous "Fix Rounds" to resolve them — powered by **dynamic LLM reflection** and **autonomous web-search documentation lookup** to resolve API/provider changes dynamically.
- **Unified Security Engine**: Dual-engine auditing using **Checkov** for deep analysis and **tfsec** for high-speed checks.
- **Financial Intelligence & Fallback Reporting**: Integrated **Infracost** monthly cost projections with fallback report generation.
- **Live Deployment**: The **Deployment Specialist** agent executes `terraform apply` and resolves cloud provider errors in real-time.

---

## 📖 Documentation

- [Multi-Agent Architecture Guide](MULTI_AGENT_ARCHITECTURE.md) — Agent roles, workflow diagrams, GitOps flow, and self-healing logic.
- [Project Structure Reference](Project-structure.md) — Industry-aligned project structure and design rationale.
- [Setup Guide](setup.md) — Step-by-step setup for Windows, Linux, and Docker.
- [Manual Test Plan](test-cases/MANUAL_TEST_PLAN.md) — End-to-end verification test cases for Phase 11 GitOps & Approval gates.

---

## 🛠️ Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your preferred model:
```env
# Example: Using Gemini (Recommended)
DEFAULT_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_key_here

# GitOps GitHub Integration (Optional for PR creation)
GITHUB_TOKEN=ghp_your_github_personal_access_token
```

### 3. Binary Requirements
Ensure `tfsec.exe` and `infracost.exe` are in the root directory for Windows. Run `.\infracost.exe auth login` to enable pricing.

---

## 🏗️ Usage

### CLI
```powershell
# For safe planning and auditing
python app/main.py --budget 150 "create a vpc with a public subnet"

# For live deployment (Self-Healing)
python app/main.py --apply --budget 150 "create a private s3 bucket in us-east-1"

# For OpenTofu engine execution
python app/main.py --engine opentofu --budget 150 "create a private s3 bucket"

# For GitOps Pull Request mode
python app/main.py --gitops --git-repo "https://github.com/my-org/terraform-iac.git" --budget 150 "create a private s3 bucket"

# For local emulation mode (using Floci)
python app/main.py --apply --test-local --budget 150 "create a private s3 bucket"

# Destroy infrastructure
python app/main.py --destroy my-project-slug
```

### Web Dashboard
```powershell
python app/dashboard.py
# Open http://localhost:5000
```
The dashboard provides:
- 🔧 **Build Tab**: Submit infrastructure requirements with budget, model selection, local emulation toggle, and **GitOps Mode drawer** for automated Pull Request generation.
- 📁 **Workspaces Tab**: View all generated projects with Terraform code, visual topology, evolution history, FinOps reports, and deployment logs.
- 🔀 **GitOps & Approval Tab**: View PR status badges, branch links, approver history, and interactive "Approve PR" and "Merge & Deploy" control buttons.
- 📜 **Audit Trail Tab**: Enterprise immutable activity log tracking every generation, PR creation, approval, and deployment event across teams.
- 🏢 **Organization Workspaces**: Create organizations, invite team members, assign roles (Owner/Admin/Member/Viewer), and switch contexts.
- 👥 **Team Management**: Manage organization members with role-based permissions — Owners/Admins can invite, promote, demote, or remove members.

### Workflow Phases
1. **Architecture**: The Architect designs the blueprint and generates a `project_slug`.
2. **Coding**: The Developer builds a modular Terraform project in `output/<slug>/`.
3. **Security Audit**: The Reviewer runs scans and attempts self-healing fixes.
4. **FinOps**: The specialist calculates costs via Infracost.
5. **GitOps & PR Synthesis**: The GitOps Coordinator creates a feature branch, commits code, and opens a structured Pull Request.
6. **Deployment / Merge**: Once approved by Org Owners/Admins, the release is merged and deployed via `terraform apply`.
7. **QA Testing**: The QA Specialist verifies live/emulated resources via automated probes and audits.

---

## 🐳 Docker Orchestration

You can run the entire platform (PostgreSQL database + web dashboard + Redis + Celery Worker + Floci local AWS) via Docker Compose:

```bash
# Build and run all services
docker compose up --build
```
This spawns:
* **`terraform-db`**: PostgreSQL 15 database storing registrations and workspaces.
* **`terraform-dashboard`**: Web dashboard listening on `http://localhost:5000`.
* **`redis`**: Cache and broker service managing the Celery task queue.
* **`worker`**: Celery worker container executing Terraform actions asynchronously in the background.
* **`floci`**: Local AWS emulation backend listening on port `4566`.

---

## 📂 Project Structure

```
terraform-ai-agent/
├── app/                    # Application entry-points
│   ├── main.py             #   CLI (thin wrapper → orchestrator)
│   └── dashboard.py        #   FastAPI Web Dashboard + Org RBAC & GitOps API
│
├── orchestrator/           # Central pipeline engine
│   ├── pipeline.py         #   run_full_pipeline() — single entry-point
│   ├── retry_handler.py    #   Self-healing loop + RetryContext
│   └── reflection.py       #   Dynamic LLM Reflection Engine with doc search
│
├── agents/                 # CrewAI agent definitions (one per role)
│   ├── terraform_architect.py
│   ├── terraform_developer.py
│   ├── security_reviewer.py
│   ├── cost_optimizer.py
│   ├── deployment_planner.py
│   ├── testing_agent.py
│   └── gitops_coordinator.py # Phase 11 GitOps & PR Coordinator
│
├── tools/                  # Deterministic tool layer
│   ├── gitops/             #   GitOpsTools (Git CLI, branch, commit, GitHub PR REST API)
│   ├── project/            #   ProjectTracker, UserTracker, OrgTracker, AuditTracker
│   ├── terraform/          #   Terraform CLI tools (init, validate, apply, destroy)
│   ├── security/           #   Checkov & tfsec auditing
│   ├── finops/             #   Infracost estimation & report builder
│   ├── testing/            #   QA behavior test execution & HTTP probes
│   └── cloud/              #   CloudSync & Floci local emulator

│   ├── deployment_planner.py
│   └── testing_agent.py     #   QA testing / verification agent
│
├── workflows/              # Task definitions for each pipeline phase
│   ├── terraform_generation.py
│   ├── terraform_validation.py
│   ├── terraform_deployment.py
│   └── terraform_testing.py #   smoke testing workflows
│
├── tools/                  # Deterministic tool integrations
│   ├── terraform/          #   TF CLI: init, validate, plan, apply
│   ├── security/           #   Checkov & tfsec scanning
│   ├── finance/            #   Infracost cost estimation
│   ├── cloud/              #   AWS readiness checks
│   ├── deployment/         #   Live deployment & testing_tools.py
│   └── project/            #   ProjectTracker, UserTracker, OrgTracker
│       └── tracker.py      #     Multi-tenant DB models + RBAC helpers
│
├── memory/                 # Failure pattern knowledge base
│   ├── failure_patterns.json  # 20+ known error→fix mappings
│   └── pattern_manager.py     # PatternManager class
│
├── llm/                    # LiteLLM abstraction layer
│   ├── config.py           #   Global retry/timeout settings
│   ├── factory.py          #   Agent LLM factory
│   ├── model_registry.py   #   Provider catalog
│   └── fallback.py         #   Multi-provider failover
│
├── workers/                # Celery async task workers
│   └── celery_worker.py    #   Background pipeline execution
│
├── static/                 # Dashboard frontend (HTML/CSS/JS)
│   ├── index.html          #   Main dashboard + Org context switcher
│   ├── login.html          #   User auth page
│   ├── app.js              #   Frontend logic + Org management
│   └── style.css           #   Glassmorphic dark theme
│
├── evaluation/             # Test cases & policy validation
├── output/                 # Generated Terraform projects
├── Dockerfile              # Containerized deployment
└── docker-compose.yml      # Multi-service orchestration
```

---

## 🏢 Multi-Tenant Organization & RBAC

### Database Models
| Model | Purpose |
|-------|----------|
| `UserModel` | User registration, password hashing, session auth |
| `OrganizationModel` | Org identity with `name`, `slug`, `owner_id` |
| `OrgMemberModel` | User↔Org membership with role (owner/admin/member/viewer) |
| `ProjectModel` | Infrastructure projects scoped by `owner_id` (personal) or `org_id` (organization) |

### RBAC Permission Matrix
| Action | Owner | Admin | Member | Viewer |
|--------|:-----:|:-----:|:------:|:------:|
| View Projects & Dashboards | ✅ | ✅ | ✅ | ✅ |
| Generate Infrastructure | ✅ | ✅ | ✅ | ❌ |
| Invite/Remove Members | ✅ | ✅ | ❌ | ❌ |
| Change Member Roles | ✅ | ✅ | ❌ | ❌ |

### Organization API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/orgs` | GET | List user's organizations |
| `/api/orgs` | POST | Create new organization |
| `/api/orgs/{id}/members` | GET | List org members |
| `/api/orgs/{id}/members` | POST | Add member by username |
| `/api/orgs/{id}/members/{uid}` | PUT | Update member role |
| `/api/orgs/{id}/members/{uid}` | DELETE | Remove member |

---

*Last Updated: 2026-08-05*
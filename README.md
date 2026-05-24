# 🤖 Universal Terraform AI Agent (Phase 9: Scaling & Local Cloud Emulation)

A powerful, interactive, and modular AI system designed to generate enterprise-grade Terraform infrastructure. Built to be **Universal**, it can be powered by cloud LLMs (Gemini, Groq, Mistral, OpenAI) or run entirely locally via **Ollama**.

---

## 🚀 Key Features

- **Multi-Agent Orchestration**: Powered by **CrewAI**, utilizing 6 specialized agents (Architect, Developer, Security Reviewer, FinOps Specialist, Deployment Planner, and QA Testing Agent) for a robust production pipeline.
- **Central Pipeline Orchestrator**: A dedicated `orchestrator/` module provides a single authoritative entry-point (`run_full_pipeline`) for both the CLI and Web Dashboard, with built-in self-healing retry logic.
- **Asynchronous Job Queue**: Powered by **Celery** and **Redis** to run heavy Terraform generation, deployment, and testing tasks concurrently in the background without blocking the web gateway.
- **Local AWS Emulation**: Integrated **Floci** (a local, high-speed AWS emulator) to test deploy mock resources (S3, EC2, RDS, Lambda, DynamoDB, SQS) completely free of charge.
- **Continuous QA Testing Agent**: A dedicated agent that runs post-apply behavior verification tests (HTTP checks, S3 read/write validations, AWS resource status audits) against emulated or real environments.
- **Failure Pattern Memory & Self-Learning**: When Terraform errors are successfully resolved via retries, the system triggers an LLM self-learning loop to automatically extract the root cause and update `failure_patterns.json` dynamically, continuously expanding its own knowledge bank.
- **Universal LLM Support**: Powered by **LiteLLM**, allowing you to swap between 100+ providers (Gemini, Groq, Mistral, OpenAI) via a single `.env` setting or the Web UI.
- **Web Dashboard**: Full-featured Flask dashboard with user authentication, project management, live agent log streaming, visual topology (Mermaid.js), and FinOps reports.
- **Modular by Default**: Automatically generates "Root + Modules" structures (e.g., separate VPC, EKS, and IAM modules) following HashiCorp best practices.
- **AI Self-Healing**: The system automatically identifies security vulnerabilities and live deployment errors, initiating autonomous "Fix Rounds" to resolve them — now enhanced with pattern-based fix guidance.
- **Unified Security Engine**: Dual-engine auditing using **Checkov** for deep analysis and **tfsec** for high-speed checks.
- **Financial Intelligence**: Integrated **Infracost** to provide instant monthly cost projections and budget guardrails.
- **Live Deployment**: The **Deployment Specialist** agent executes `terraform apply` and resolves cloud provider errors in real-time.

---

## 📖 Documentation

- [Multi-Agent Architecture Guide](MULTI_AGENT_ARCHITECTURE.md) — Agent roles, workflow diagrams, and self-healing logic.
- [Project Structure Reference](Project-structure.md) — Industry-aligned project structure and design rationale.
- [Setup Guide](setup.md) — Step-by-step setup for Windows, Linux, and Docker.

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

# Example: Using Mistral (Best for Code)
# DEFAULT_MODEL=mistral/mistral-large-latest
# MISTRAL_API_KEY=your_key_here
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
- 🔧 **Build Tab**: Submit infrastructure requirements with budget and AI model selection. Supports checking a toggle to force "Local Emulation Mode (Floci)".
- 📁 **Workspaces Tab**: View all generated projects with Terraform code, visual topology, evolution history, FinOps reports, and deployment logs.
- 📊 **Dashboard Metrics**: Total projects, live deployments, monthly cloud spend, and security risk counts.

### Workflow Phases
1. **Architecture**: The Architect designs the blueprint and generates a `project_slug`.
2. **Coding**: The Developer builds a modular Terraform project in `output/<slug>/`.
3. **Security Audit**: The Reviewer runs scans and attempts self-healing fixes.
4. **FinOps**: The specialist calculates costs via Infracost.
5. **Deployment**: The specialist executes `terraform apply` and heals any live API errors.
6. **QA Testing**: The QA Specialist verifies the live/emulated resources via automated HTTP probes, S3 read/write checks, and API resource status audits.

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

### Push to Container Registry
To distribute the built agent image:
```bash
docker login
docker tag terraform-ai-agent-agent:latest shubham554/terraform-ai-agent:v1
docker push shubham554/terraform-ai-agent:v1
```

### Run Single CLI container
```bash
# Build the CLI image
docker build -t terraform-ai-agent .

# Generate and audit (no cloud deployment)
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --budget 100 "create a vpc with a public subnet"
```

---

## 📂 Project Structure

```
terraform-ai-agent/
├── app/                    # Application entry-points
│   ├── main.py             #   CLI (thin wrapper → orchestrator)
│   └── dashboard.py        #   Flask Web Dashboard
│
├── orchestrator/           # Central pipeline engine
│   ├── pipeline.py         #   run_full_pipeline() — single entry-point
│   └── retry_handler.py    #   Self-healing loop + RetryContext
│
├── agents/                 # CrewAI agent definitions (one per role)
│   ├── terraform_architect.py
│   ├── terraform_developer.py
│   ├── security_reviewer.py
│   ├── cost_optimizer.py
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
│   └── project/            #   ProjectTracker (SQLite/PostgreSQL)
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
├── static/                 # Dashboard frontend (HTML/CSS/JS)
├── evaluation/             # Test cases & policy validation
├── output/                 # Generated Terraform projects
├── Dockerfile              # Containerized deployment
└── docker-compose.yml      # Multi-service orchestration
```

---

*Last Updated: 2026-05-24*
# 🤖 Universal Terraform AI Agent (Phase 5: Self-Healing Deployment)

A powerful, interactive, and modular AI system designed to generate enterprise-grade Terraform infrastructure. Built to be **Universal**, it can be powered by cloud LLMs (Gemini, Groq, Mistral) or run entirely locally via **Ollama**.

---

## 🚀 Key Features

- **Multi-Agent Orchestration**: Powered by **CrewAI**, utilizing specialized agents (Architect, Developer, Security Reviewer, FinOps Specialist) for a robust production pipeline.
- **Universal LLM Support**: Powered by **LiteLLM**, allowing you to swap between 100+ providers (Gemini, Groq, Mistral, OpenAI) via a single `.env` setting.
- **Modular by Default**: Automatically generates "Root + Modules" structures (e.g., separate VPC, EKS, and IAM modules) following HashiCorp best practices.
- **AI Self-Healing**: The system automatically identifies security vulnerabilities and live deployment errors, initiating autonomous "Fix Rounds" to resolve them.
- **Unified Security Engine**: Dual-engine auditing using **Checkov (Docker)** for deep analysis and **tfsec** for high-speed checks.
- **Financial Intelligence**: Integrated **Infracost (Docker)** to provide instant monthly cost projections and budget guardrails.
- **Live Deployment**: Introducing the **Deployment Specialist** agent capable of running `terraform apply` and resolving cloud provider errors (AMI mismatches, quota limits, etc.) in real-time.

---

## 📖 Documentation

For a detailed breakdown of the multi-agent system, see the [Multi-Agent Architecture Guide](MULTI_AGENT_ARCHITECTURE.md).

---

## 🛠️ Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your preferred model:
```env
# Example: Using Groq (Fastest)
DEFAULT_MODEL=groq/llama-3.3-70b-versatile
GROQ_API_KEY=your_key_here

# Example: Using Mistral (Best for Code)
# DEFAULT_MODEL=mistral/codestral-latest
# MISTRAL_API_KEY=your_key_here
```

### 3. Binary Requirements
Ensure `tfsec.exe` and `infracost.exe` are in the root directory for Windows. Run `.\infracost.exe auth login` to enable pricing.

---

## 🏗️ Usage

Run the **Phase 5 Multi-Agent Runner**:
```powershell
# For safe planning and auditing
python crew_runner.py --budget 150 "create a vpc with a public subnet"

# For live deployment (Self-Healing)
python crew_runner.py --apply --budget 150 "create a private s3 bucket in us-east-1"
```

### Workflow Phases:
1.  **Architecture**: The Architect designs the blueprint and generates a `project_slug`.
2.  **Coding**: The Developer builds a modular Terraform project in `output/<slug>/`.
3.  **Security Audit**: The Reviewer runs scans and attempts self-healing fixes.
4.  **FinOps**: The specialist calculates costs using Dockerized Infracost.
5.  **Deployment (New)**: The specialist executes `terraform apply` and heals any live API errors.

---

## 📂 Project Structure

- **`crew_runner.py`**: The entry point for the Multi-Agent workflow.
- **`agents.py` & `tasks.py`**: Definitions of the AI team and their specific goals.
- **`tools/`**: Specialized tools for Terraform management, security, and cost estimation.
- **`output/`**: Directory containing your generated, validated, and audited Terraform projects.
python crew_runner.py --budget 250 "Your infra requirement" 
---

*Last Updated: 2026-04-22*
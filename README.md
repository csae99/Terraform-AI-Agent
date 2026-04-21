# 🤖 Universal Terraform AI Agent (Phase 4: Multi-Agent)

A powerful, interactive, and modular AI system designed to generate enterprise-grade Terraform infrastructure. Built to be **Universal**, it can be powered by cloud LLMs (Gemini, Groq, Mistral) or run entirely locally via **Ollama**.

---

## 🚀 Key Features

- **Multi-Agent Orchestration**: Powered by **CrewAI**, utilizing specialized agents (Architect, Developer, Security Reviewer, FinOps Specialist) for a robust production pipeline.
- **Universal LLM Support**: Powered by **LiteLLM**, allowing you to swap between 100+ providers (Gemini, Groq, Mistral, OpenAI) via a single `.env` setting.
- **Modular by Default**: Automatically generates "Root + Modules" structures (e.g., separate VPC, EKS, and IAM modules) following HashiCorp best practices.
- **AI Self-Healing**: The system automatically identifies security vulnerabilities and initiates "Fix Rounds" to patch critical issues autonomously.
- **Unified Security Engine**: Dual-engine auditing using **Checkov (Docker)** for deep analysis and **tfsec (Local)** for high-speed checks.
- **Financial Intelligence**: Integrated **Infracost** to provide instant monthly cost projections and budget guardrails.
- **Windows Hardened**: Optimized for PowerShell, handling deep paths, Unicode characters, and standalone binaries seamlessly.

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

Run the **Phase 4 Multi-Agent Runner**:
```powershell
python crew_runner.py --budget 150 "create a production grade eks cluster in a private vpc"
```

### Workflow Phases:
1.  **Architecture**: The Architect designs the blueprint and generates a `project_slug`.
2.  **Coding**: The Developer builds a modular Terraform project in `output/<slug>/`.
3.  **Security Audit**: The Reviewer and Auditor run scans and attempt self-healing fixes.
4.  **FinOps**: The specialist calculates costs and checks against your `--budget`.

---

## 📂 Project Structure

- **`crew_runner.py`**: The entry point for the Multi-Agent workflow.
- **`agents.py` & `tasks.py`**: Definitions of the AI team and their specific goals.
- **`tools/`**: Specialized tools for Terraform management, security, and cost estimation.
- **`output/`**: Directory containing your generated, validated, and audited Terraform projects.
python crew_runner.py --budget 250 "Your infra requirement" 
---

*Last Updated: 2026-04-22*
# Universal Terraform AI Agent

A powerful, interactive, and modular AI agent designed to generate enterprise-grade Terraform infrastructure. Built to be **Universal**, it can be powered by cloud LLMs (Gemini, OpenAI, Claude) or run entirely locally via **Ollama**.

## 🚀 Key Features

- **Universal LLM Support**: Powered by **LiteLLM**, allowing you to swap between 100+ providers via a single setting.
- **Robust Fallback Engine**: Integrated official Google Generative AI SDK fallback ensures 100% reliability for Gemini users.
- **Local Model Ready**: Natively supports **Ollama** (Docker or Desktop) for private, local-only infrastructure generation.
- **Modular by Default**: Automatically generates "Root + Modules" structures (e.g., separate VPC, EKS, and IAM modules) for maximum reusability.
- **Unified Security Engine**: Dual-engine auditing using **Checkov (Docker)** for deep analysis and **tfsec (Local)** for high-speed checks.
- **AI Self-Healing**: The agent automatically identifies its own security vulnerabilities and initiates a "Fix Round" to patch critical issues autonomously.
- **Interactive Requirement Gathering**: Simple CLI interface that gathers your infrastructure needs dynamically.
- **Automated Documentation**: Every project generated includes a tailored `README.md` with step-by-step deployment instructions.

## 🛠️ Setup

### 1. Install Dependencies
Ensure you are using Python 3.9+ (Tested up to 3.14).
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env` and configure your preferred model:
```env
# Example: Using Gemini (Flash)
DEFAULT_MODEL=gemini/gemini-1.5-flash
GEMINI_API_KEY=your_key_here

# Example: Using Local Ollama
# DEFAULT_MODEL=ollama/tinyllama
```

### 3. (Optional) Local LLM Setup (Docker)
To run entirely locally, start the Ollama container and pull a model:
```powershell
docker run -d -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama pull tinyllama
```

### 4. (Optional) Security Binary
Verify that `tfsec.exe` is in the root directory for fast scans. For deep scans, ensured Docker is running.

## 📖 Usage

Run the interactive generator:
```powershell
python fallback_generator.py
```

1. **Describe your infra**: "A scalable EKS cluster with managed nodes and a public VPC."
2. **Review Output**: The agent will create a project-specific folder in `output/`.
3. **Deploy**: Follow the instructions in the generated `README.md` inside your project folder.

## 🏗️ Project Structure

- **`fallback_generator.py`**: The main Unified Agent script.
- **`tools/terraform_tools.py`**: Core utilities for file management and terraform validation.
- **`output/`**: Dedicated subdirectories for each generated infrastructure project.
- **`requirements.txt`**: Consolidated list of all necessary libraries (LiteLLM, Google SDK, etc.).

## 🛡️ Windows Compatibility
This project is hardened for Windows environments, including:
- **Unicode Resilience**: Optimized to prevent encoding errors in the terminal.
- **Path Handling**: Fully supports deep, recursive directory structures for Terraform modules.
 
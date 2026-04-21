# Terraform AI Agent - Setup Guide

This guide provides step-by-step instructions for setting up the Universal Terraform AI Agent on both Windows and Linux.

## 🛠️ Core Requirements (All Platforms)

1.  **Python 3.9+**: The core engine of the agent.
2.  **Terraform CLI**: Required for infrastructure validation and deployment.
3.  **Docker**: Required for Deep Security Auditing (Checkov) and local LLMs (Ollama).
4.  **API Keys**: A Gemini API key (Primary) or OpenAI/Claude key.

---

## 🪟 Windows Setup (PowerShell)

### 1. Basic Environment
```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Security & Financial Tools (Binaries)
These tools are provided as standalone binaries for Windows to avoid complex build requirements.
- **tfsec** (Fast Scan): [Download tfsec-windows-amd64.exe](https://github.com/aquasecurity/tfsec/releases) and place it in the root as `tfsec.exe`.
- **Infracost** (Cost Scan): [Download infracost-windows-amd64.zip](https://github.com/infracost/infracost/releases), extract, and place it in the root as `infracost.exe`.
- **Checkov** (Deep Scan): Handled via Docker. No local installation needed.

### 3. Authentication
```powershell
# Authenticate Infracost (Free API Key)
.\infracost.exe auth login
```

---

## 🐧 Linux Setup (Bash)

### 1. Basic Environment
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Tools & Binaries
On Linux, we recommend using the direct installers or standalone binaries.

**tfsec (Fast Scan):**
```bash
curl -L -o tfsec https://github.com/aquasecurity/tfsec/releases/latest/download/tfsec-linux-amd64
chmod +x tfsec
sudo mv tfsec /usr/local/bin/
```

**Infracost (Cost Scan):**
```bash
curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh
```

**Checkov (Deep Scan):**
Handled via Docker. Ensure Docker is installed and your user is in the `docker` group.
```bash
docker pull bridgecrew/checkov:latest
```

### 3. Authentication
```bash
infracost auth login
```

---

## 🔑 Environment Secrets (.env)

Create a `.env` file in the root directory:
```env
# Active Model
DEFAULT_MODEL=gemini/gemini-1.5-flash

# Keys
GEMINI_API_KEY=your_key_here
# INFRACOST_API_KEY=your_key_optional

# Phase 3: Cloud Sync (Required for Enterprise Mode)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
```

---

## ☁️ Phase 3: Enterprise Cloud Sync

When you request "Production" or "Enterprise" infrastructure, the agent automatically enables **Remote State Management**.

### 1. Requirements
- An active AWS IAM User with permissions to manage S3 and DynamoDB.
- Credentials added to your `.env` file (as shown above).

### 2. The "Bootstrap" Workflow
To prevent "Chicken and Egg" problems, the agent creates a `bootstrap/` directory for Enterprise projects.
1.  **Navigate** to the project folder: `cd output/<project_slug>/bootstrap`
2.  **Initialize & Apply**: `terraform init; terraform apply`
3.  This creates the S3 Bucket (versioned & encrypted) and the DynamoDB Table for state locking.
4.  **Main Deployment**: You can then run `terraform init` in the root project folder to connect to your new remote backend.

### 3. Naming Convention
By default, the agent enforces a `-tf-state` suffix for all buckets it manages, ensuring your cloud account remains organized.

---
python crew_runner.py --budget 250 "Your infra requirement" 
*This guide is updated automatically as new backend capabilities are added.*

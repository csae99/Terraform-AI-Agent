# Terraform AI Agent - Setup Guide

This guide provides step-by-step instructions for setting up the Universal Terraform AI Agent on both Windows and Linux.

## 🛠️ Core Requirements (All Platforms)

1.  **Python 3.9+**: The core engine of the agent.
2.  **Terraform CLI**: Required for infrastructure validation and deployment.
3.  **Docker**: Essential for FinOps (Infracost) and Security (Checkov).
4.  **AWS CLI**: Required for live deployments in Phase 5.
5.  **API Keys**: Gemini API key (Primary) and an Infracost API token.

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

### 2. Security & Financial Tools (Dockerized)
The platform now uses Dockerized versions of **Infracost** and **Checkov** to ensure consistency.
- **Docker**: Ensure Docker Desktop is running.
- **Infracost API Key**: Register at [infracost.io](https://www.infracost.io/) and add your key to the `.env` file.
- **Checkov**: The agent will automatically pull and run the `bridgecrew/checkov` image.

### 3. Authentication
```powershell
# Authenticate Infracost (Free API Key)
# Note: Ensure INFRACOST_API_KEY is set in your .env file
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

**Infracost & Checkov (Docker):**
No manual installation is required. Ensure your user has permissions to run Docker:
```bash
sudo usermod -aG docker $USER
```
The agent will pull `infracost/infracost` and `bridgecrew/checkov` automatically.

### 3. Authentication
```bash
# Ensure INFRACOST_API_KEY is set in your .env file
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
## 🚀 Phase 5: Self-Healing Deployment

To trigger a live deployment, use the `--apply` flag:
```powershell
python crew_runner.py --apply --budget 100 "create an s3 bucket"
```

The agent will:
1.  **Generate** the modular Terraform code.
2.  **Audit** for security (Checkov) and costs (Infracost).
3.  **Plan & Apply**: It will first run `terraform plan`. If successful, it proceeds to `terraform apply`.
4.  **Self-Heal**: If a cloud provider error occurs (e.g., `BucketAlreadyExists` or `InvalidAMI`), the agent captures the log, identifies the fix, and automatically retries the deployment.

---

## 🐳 Docker (Zero-Install Setup)

If you don't want to install Python, Terraform, Infracost, etc. manually, use Docker:

```bash
# 1. Build the image (one-time)
docker build -t terraform-ai-agent .

# 2. Create your .env file from the example
cp .env.example .env
# Edit .env with your API keys

# 3. Run the agent
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --budget 100 "create a vpc with a public subnet"

# 4. Live deploy
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --apply --budget 100 "create a private s3 bucket"

# 5. Destroy
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --destroy my-project-slug
```

> **Tip**: For AWS credentials, either add them to `.env` or mount your AWS config:
> ```bash
> docker run --rm -it --env-file .env \
>   -v $(pwd)/output:/app/output \
>   -v ~/.aws:/root/.aws:ro \
>   terraform-ai-agent --apply "create an s3 bucket"
> ```

---
*Last Updated: 2026-04-25*

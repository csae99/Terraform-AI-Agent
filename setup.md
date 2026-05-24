# Terraform AI Agent - Setup Guide (Phase 9)

This guide provides step-by-step instructions for setting up the Universal Terraform AI Agent on both Windows and Linux.

## 🛠️ Core Requirements (All Platforms)

1.  **Python 3.9+**: The core engine of the agent.
2.  **Terraform CLI**: Required for infrastructure validation and deployment.
3.  **Docker**: Essential for FinOps (Infracost), Security (Checkov), and local cloud emulation (Floci).
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
DEFAULT_MODEL=gemini/gemini-2.0-flash

# Keys
GEMINI_API_KEY=your_key_here
# MISTRAL_API_KEY=your_key_optional
# INFRACOST_API_KEY=your_key_optional

# Cloud Sync (Required for Live Deployments)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret

# Dashboard
FLASK_SECRET_KEY=your_random_secret

# Redis Broker Url (Optional, defaults to redis://redis:6379/0)
REDIS_URL=redis://localhost:6379/0

# Enable Local AWS Emulation Mode (Floci)
TEST_LOCAL=true
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
## 🚀 Self-Healing Deployment

To trigger a live deployment, use the `--apply` flag:
```powershell
python app/main.py --apply --budget 100 "create an s3 bucket"
```

The agent will:
1.  **Generate** the modular Terraform code.
2.  **Audit** for security (Checkov) and costs (Infracost).
3.  **Plan & Apply**: It will first run `terraform plan`. If successful, it proceeds to `terraform apply`.
4.  **Self-Heal**: If a cloud provider error occurs (e.g., `BucketAlreadyExists` or `InvalidAMI`), the Pattern Memory is consulted for known fixes, and the agent automatically retries with targeted guidance.

---

## 🖥️ Web Dashboard

Launch the web dashboard for a full GUI experience:
```powershell
python app/dashboard.py
# Open http://localhost:5000
```

Features:
- **Build Interface**: Submit infrastructure requirements with budget constraints, choice of AI model configuration, and credentials sync.
- **New Workspace Toggle**: Next to "Live Deploy", the "New Workspace" toggle checkbox allows the user to decide whether to overwrite the existing workspace project folder in-place or generate a fresh workspace sequential slug (e.g. `<slug>-1`, `<slug>-2`) to prevent state loss.
- **FinOps Presentation Layer**: Integrated with `marked.js` to parse cost estimation markdown files dynamically into responsive HTML tables, highlighting budget status compliances (danger/success) inside glowing glassmorphism alert cards.
- **Workspace Explorer**: Browse generated projects with tabbed code viewers, visual Mermaid topology, version-controlled evolution diff comparisons, and raw deployment logs.
- **User Authentication**: Secure user register, login, and project isolation database logic.

---

## 🐳 Docker Compose Orchestration

Instead of launching individual containers, you can use **Docker Compose** to run the complete multi-service database-backed dashboard environment:

### 1. Build and Start Services
```bash
docker compose up --build
```
This launches:
- **`terraform-db`**: A PostgreSQL 15 database container mapped to a persistent Docker volume (`postgres_data`), storing user registrations and project history.
- **`redis`**: A Redis broker running on port `6379` managing the Celery task queue.
- **`floci`**: Local AWS emulator mapping all services on port `4566`.
- **`worker`**: Background Celery worker executing tasks concurrently.
- **`terraform-dashboard`**: The FastAPI-based dashboard application server exposed on port `5000`.

### 2. Local Cloud Emulation Mode
By setting `TEST_LOCAL=true` in the environment, the dashboard and worker containers route all AWS-targeted Terraform scripts through Floci's endpoint `http://floci:4566` via automatic HCL configuration injection.

### 3. Continuous QA Testing & Self-Learning
- A dedicated **QA Testing Agent** executes HTTP checks, S3 read/write checks, and AWS resource status tests immediately after live/emulated deployment.
- When self-healing succeeds, the **Dynamic Self-Learning Loop** uses the LLM to extract root causes and update `failure_patterns.json` dynamically.

### 4. Native In-Container Execution
When running inside Docker (`RUNNING_IN_DOCKER=true`), the backend automatic environment detection configures the agent tools (e.g., Infracost, Checkov, and tfsec) to run natively within the container instead of making host-to-container calls. This ensures maximum compatibility and eliminates host filesystem binary issues.

### 5. Registry Distribution (Pushing to Docker Hub)
To tag and publish the built agent image to a container registry:
```bash
# 1. Log in to your Docker Hub registry
docker login

# 2. Tag the locally built image (e.g. for user 'shubham554')
docker tag terraform-ai-agent-agent:latest shubham554/terraform-ai-agent:v1

# 3. Push it to Docker Hub
docker push shubham554/terraform-ai-agent:v1
```
*Note: In `docker-compose.yml`, the image key can be set to `shubham554/terraform-ai-agent:v1` to run the tagged registry image directly.*

---

## 🐳 Running Single CLI Containers

If you only want to use the CLI agent inside Docker:

```bash
# 1. Build the CLI image
docker build -t terraform-ai-agent .

# 2. Run the generator
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --budget 100 "create a vpc with a public subnet"

# 3. Live deploy
docker run --rm -it --env-file .env -v $(pwd)/output:/app/output \
  terraform-ai-agent --apply --budget 100 "create a private s3 bucket"
```

---
*Last Updated: 2026-05-24*

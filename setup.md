# 🛠️ Autonomous Infrastructure Platform - Setup Guide (Phase 15: Kubernetes-Native Control Plane & GitOps)

This guide provides step-by-step instructions for setting up the Universal Autonomous Infrastructure Platform on Windows, Linux, macOS, Docker, and Kubernetes.

## 🛠️ Core Requirements (All Platforms)

1. **Python 3.9+**: The core engine of the agent.
2. **IaC Engines**: **HashiCorp Terraform** (`terraform`) and/or **Linux Foundation OpenTofu** (`tofu`).
3. **Git CLI**: Required for branch creation and automated Pull Requests.
4. **Docker**: Essential for FinOps (Infracost), Security (Checkov), OPA Policy-as-Code, and local cloud emulation (Floci).
5. **Kubernetes & Helm (Phase 15)**: `kubectl` v1.24+ and `helm` v3.8+ for deploying CRDs and the operator controller.
6. **AWS / Azure / GCP Cloud CLI**: Required for live multi-cloud deployments and regional failover.
7. **Payment Gateways**: Razorpay (`RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`) and/or Stripe (`STRIPE_SECRET_KEY`).
8. **SSO Identity Providers (Optional)**: Microsoft Entra ID, Okta, Google Workspace, or Auth0.
9. **API Keys**: LLM API key (Google Gemini, OpenAI, Claude, Mistral, Groq, ZenMux), Infracost API token, and optional GitHub Personal Access Token (for GitOps PRs).

---

## 🗺️ Platform Deployment Modes Matrix

The platform is engineered to run in 4 distinct operational modes depending on your scale and infrastructure environment:

| Deployment Mode | Primary Use Case | Database & State | Task Execution | IaC Engine | Launch Command |
|:---|:---|:---|:---|:---|:---|
| **Mode 1: Local Developer** | Solo development, rapid testing, and offline sandbox exploration | SQLite (`terraform_agent.db`) + In-Memory Vector Search | Synchronous thread worker pool | Local `terraform.exe` / `tofu.exe` | `python app/dashboard.py` |
| **Mode 2: Single-Node Docker** | Team staging, CI/CD runners, and integration testing | PostgreSQL 15 + `pgvector` container + Local Floci AWS | Asynchronous Celery workers via Redis | Containerized Terraform / OpenTofu | `docker compose up --build` |
| **Mode 3: Kubernetes Control Plane** | Enterprise platform engineering teams & cluster GitOps | Kubernetes CRDs + Etcd state storage | Async Operator Reconciler Loop | Ephemeral in-cluster pods / jobs | `kubectl apply -k k8s/` or Helm 3 |
| **Mode 4: Multi-Tenant Enterprise SaaS** | Production SaaS with SSO, payment gateways & SLA monitoring | Managed RDS PostgreSQL HA + S3 Remote State Locking | Distributed Celery cluster + Redis Sentinel | Dual-engine with automatic fallback | Helm Chart + Ingress + Entra ID/Okta |

> [!TIP]
> **Quickstart Recommendation**: Start with **Mode 1 (Local Developer)** or **Mode 2 (Single-Node Docker)** to test prompts and verify configurations before deploying to a Kubernetes cluster.

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

### 2. IaC Engine Setup (Terraform / OpenTofu)
You can install either or both engines via Chocolatey or Scoop:
```powershell
# Terraform
choco install terraform -y

# OpenTofu (Optional)
choco install opentofu -y
```

### 3. Security & Financial Tools (Dockerized)
The platform uses Dockerized versions of **Infracost** and **Checkov** to ensure consistency.
- **Docker**: Ensure Docker Desktop is running.
- **Infracost API Key**: Register at [infracost.io](https://www.infracost.io/) and add your key to the `.env` file.
- **Checkov**: The agent will automatically pull and run the `bridgecrew/checkov` image.

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

### 2. IaC Engines & Binaries
Install Terraform or OpenTofu:
```bash
# OpenTofu
snap install --classic opentofu

# Terraform
sudo apt-get install terraform
```

**tfsec (Fast Scan):**
```bash
curl -L -o tfsec https://github.com/aquasecurity/tfsec/releases/latest/download/tfsec-linux-amd64
chmod +x tfsec
sudo mv tfsec /usr/local/bin/
```

---

## 🔑 Environment Secrets (.env)

Create a `.env` file in the root directory:
```env
# Active Model
DEFAULT_MODEL=gemini/gemini-2.0-flash

# LLM API Keys
GEMINI_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# ZENMUX_API_KEY=your_key_here
# INFRACOST_API_KEY=your_key_optional

# Payment Gateways (Stripe & Razorpay)
DEFAULT_PAYMENT_GATEWAY=razorpay
RAZORPAY_KEY_ID=rzp_test_your_id
RAZORPAY_KEY_SECRET=your_secret_here

STRIPE_PUBLISHABLE_KEY=pk_test_your_key
STRIPE_SECRET_KEY=sk_test_your_secret

# Default IaC Engine ('terraform' or 'opentofu')
DEFAULT_IAC_ENGINE=terraform

# Cloud Sync (Required for Live Deployments)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=us-east-1

# Dashboard
FLASK_SECRET_KEY=your_random_secret

# Redis Broker Url (Optional, defaults to redis://localhost:6379/0)
REDIS_URL=redis://localhost:6379/0

# Enable Local AWS Emulation Mode (Floci)
TEST_LOCAL=true
```

---

## 👑 Super-Admin Account Bootstrap & Operations Console

The platform provides a dedicated, enterprise-grade **Platform Operations Console** (`/admin`) reserved exclusively for Super-Administrators.

### 1. Bootstrap a Super-Admin Account (CLI & Auto-Bootstrap)

> [!IMPORTANT]
> **Automatic Super-Admin Bootstrapping (Kubernetes & Docker Modes)**:
> When the platform starts up in Kubernetes or Docker Compose, the database engine **automatically creates the default Super-Admin user** on initial launch:
> - **Username**: `admin` (or via `DEFAULT_ADMIN_USER`)
> - **Password**: `StrongPassword123!` (or via `DEFAULT_ADMIN_PASSWORD`)
> - **Email**: `admin@platform.io`
> 
> You do **not** need to manually run any script or exec into pods to create the Super-Admin account in Kubernetes. Normal users who subsequently register via the Web UI register form (`/login`) are automatically assigned standard user privileges (`is_superuser = False`).
>
> The CLI utility `scripts/create_admin.py` is available for offline SQLite exploration (Mode 1) or for promoting/demoting existing users from the command line:

```powershell
# Create a new Super-Admin account (or promote existing)
python scripts/create_admin.py --username admin --password "StrongPassword123!" --email admin@platform.io

# Or promote an existing user account to Super-Admin
python scripts/create_admin.py --promote existing_username

# List all users, roles, and status
python scripts/create_admin.py --list
```

### 2. Access the Operations Console
1. Launch the web server:
   ```powershell
   python app/dashboard.py
   ```
2. Open **[http://localhost:5000/login](http://localhost:5000/login)** (or `http://127.0.0.1:5000/login`) in your browser.
3. Sign in with your Super-Admin credentials (`admin` / `StrongPassword123!`).
4. Once authenticated:
   - Click the glowing purple **⚡ Admin Console** link in the top navigation header, or
   - Navigate directly to **[http://localhost:5000/admin](http://localhost:5000/admin)**.

### 3. Key Operations in the Console
- **Tenant & User Management**: View all platform users, suspend malicious/compromised accounts, reactivate accounts, or grant/revoke Super-Admin privileges.
- **Organization Plan Overrides**: Instantly upgrade or downgrade any organization between **Free**, **Pro**, and **Enterprise** tiers with automated quota bypass.
- **LLM Economics & Router Health**: Real-time telemetry monitoring token consumption, costs, and response latency across providers (Gemini, OpenAI, Claude, ZenMux, OpenRouter).
- **Kubernetes Fleet Status**: Inspect health status, node counts, and CRD reconcilers across all registered Kubernetes clusters.
- **Global Immutable Audit Trail**: Review and filter all platform-wide events (user registrations, project builds, approvals, and plan modifications) with one-click JSON export.

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
- **Organization Workspaces** *(Phase 10)*: Create organizations, invite team members by username, assign roles (Owner/Admin/Member/Viewer), and switch between Personal and Org contexts seamlessly via the header dropdown.
- **Team Management** *(Phase 10)*: Manage organization members with role-based permissions. Viewers are read-only; Members can generate infrastructure; Owners/Admins can invite and manage team members.

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

## ☸️ Kubernetes-Native Control Plane Setup (Phase 15)

Phase 15 allows you to run the complete platform as an enterprise Kubernetes Operator and Control Plane with continuous drift healing, automated GitOps pull requests, LLM model routing, and an in-cluster observability stack (Prometheus, Grafana, Alertmanager).

> [!NOTE]
> **Cross-Machine Compatibility**:
> These instructions are verified to run identically on any local machine (Windows, macOS, Linux) or cloud provider using:
> - **Docker Desktop Kubernetes** (Windows/macOS - recommended for local exploration)
> - **Minikube** (`minikube start`)
> - **KinD** (`kind create cluster`)
> - **K3s / MicroK8s**
> - **Managed Cloud Kubernetes** (AWS EKS, GCP GKE, Azure AKS)

---

### Step 1: Build the Platform Container Image
Before applying the manifests, build the unified platform container image from the repository root. This bundles Python 3.11, OpenTofu, Terraform, Infracost, Checkov, and the web console into a local image tagged `terraform-ai-agent:k8s-local`:

```bash
# Standard Docker Desktop / Linux / macOS:
docker build -t terraform-ai-agent:k8s-local .

# If using Minikube (build directly inside Minikube's Docker daemon):
minikube image build -t terraform-ai-agent:k8s-local .

# If using KinD:
docker build -t terraform-ai-agent:k8s-local .
kind load docker-image terraform-ai-agent:k8s-local
```

---

### Step 2: Install Custom Resource Definitions (CRDs)
Apply the 4 OpenAPI v3 Custom Resource Definitions to the cluster:

```bash
kubectl apply -f k8s/crds/
```

Verify that the CRDs are registered:
```bash
kubectl get crds | grep platform.terraform-ai.io
# Output:
# platformprojects.platform.terraform-ai.io
# policies.platform.terraform-ai.io
# terraformagents.platform.terraform-ai.io
# workflows.platform.terraform-ai.io
```

---

### Step 3: Configure Environment Secrets (Optional but Recommended)
Create the dedicated `terraform-ai-system` namespace and configure your API keys (Google Gemini, OpenAI, Claude, Infracost, etc.):

```bash
# 1. Create namespace
kubectl create namespace terraform-ai-system

# 2. Store API keys as a Kubernetes Secret
kubectl create secret generic terraform-ai-secrets -n terraform-ai-system \
  --from-literal=GEMINI_API_KEY="your_gemini_api_key" \
  --from-literal=OPENAI_API_KEY="your_openai_api_key_optional" \
  --from-literal=INFRACOST_API_KEY="your_infracost_key_optional" \
  --from-literal=TEST_LOCAL="true"
```
*(If you skip this step, the platform will start cleanly using mock/local emulation mode).*

---

### Step 4: Deploy the Platform Control Plane
You can deploy the platform using **Option A (Pure `kubectl` - No Helm required)** or **Option B (Helm 3)**:

#### Option A: Direct `kubectl` Manifests (No Helm Required)
If you do not have Helm installed, apply the standalone Kubernetes manifests directly:

```bash
# Deploy RBAC, PostgreSQL, Redis, Dashboard, and Operator:
kubectl apply -f k8s/manifests/
```

#### Option B: Deploy via Helm 3
If you use Helm, deploy the parameterized Helm chart:

```bash
# Deploy with default values (auto-creates Super-Admin and configures services)
helm upgrade --install terraform-ai ./k8s/helm \
  --namespace terraform-ai-system \
  --create-namespace \
  --values ./k8s/helm/values.yaml
```

---

### Step 5: Deploy Monitoring & Observability Stack (Prometheus, Grafana & Alertmanager)
Deploy the in-cluster Prometheus time-series scraper, Grafana dashboard engine, and Alertmanager notification dispatcher:

```bash
kubectl apply -f k8s/monitoring/
```

---

### Step 6: Verify Running Pods & Services
Verify that all 7 platform workloads are running in `terraform-ai-system`:

```bash
kubectl get pods,services -n terraform-ai-system
```

Expected output:
```text
NAME                                             READY   STATUS    RESTARTS   AGE
pod/alertmanager-687998d5c5-hbjjx                1/1     Running   0          5m
pod/grafana-8446c7464b-qfnsb                     1/1     Running   0          5m
pod/prometheus-56d449c689-dhnlr                  1/1     Running   0          5m
pod/terraform-ai-dashboard-6c98b5c75b-rzxl6      1/1     Running   0          5m
pod/terraform-ai-db-69cc88b785-9jsmd             1/1     Running   0          5m
pod/terraform-ai-redis-86b6b5cb8f-8jtbb          1/1     Running   0          5m
pod/terraform-ai-terraform-ai-operator-67555-q   1/1     Running   0          5m
```

---

### Step 7: Access the Web Console & Port Forwarding

#### In Docker Desktop (Windows & macOS):
All services with `type: LoadBalancer` automatically bind to `localhost`:
- **Web Dashboard & Admin Console**: **`http://localhost:5000`**
- **Prometheus Metrics Scraper**: **`http://localhost:9090`**
- **Grafana Dashboards**: **`http://localhost:3000`**
- **Alertmanager Dispatcher**: **`http://localhost:9093`**

#### In Minikube, KinD, or Remote/Cloud Clusters:
- **Minikube**: Run `minikube tunnel` in an administrator terminal to route LoadBalancers, OR use port-forwarding.
- **Universal Port-Forwarding (Works on ANY machine/cluster)**:
  ```bash
  # Web Dashboard (Port 5000)
  kubectl port-forward svc/terraform-ai-dashboard 5000:5000 -n terraform-ai-system

  # Observability Tools (Optional)
  kubectl port-forward svc/prometheus 9090:9090 -n terraform-ai-system
  kubectl port-forward svc/grafana 3000:3000 -n terraform-ai-system
  kubectl port-forward svc/alertmanager 9093:9093 -n terraform-ai-system
  ```

---

### Step 8: Automatic Super-Admin Login vs Normal User Signup

The platform implements strict role-based separation:

1. **👑 Automatic Super-Admin Creation (On First Launch)**:
   - When the `terraform-ai-dashboard` pod starts, it initializes the database tables and **automatically creates the primary Super-Admin account**:
     - **Username**: `admin` (customizable via `DEFAULT_ADMIN_USER` in `values.yaml` or manifests)
     - **Password**: `StrongPassword123!` (customizable via `DEFAULT_ADMIN_PASSWORD`)
     - **Email**: `admin@platform.io`
   - Open **`http://localhost:5000/login`**, enter `admin` / `StrongPassword123!`, and you will immediately have full access to the **Platform Operations Command Center** at **`http://localhost:5000/admin`**.

2. **👤 Normal User Sign-Up (Standard Users)**:
   - Normal developers and team members register by navigating to **`http://localhost:5000/login`** and clicking the **Register** tab.
   - Newly registered users are automatically assigned standard tenant privileges (`is_superuser = False`).
   - Normal users can generate infrastructure workspaces, inspect Mermaid diagrams, and trigger plans, but are **cleanly blocked (HTTP 403)** from accessing administrative routes (`/admin`, `/api/admin/*`).
   - Super-Admins can view, suspend, reactivate, or promote any standard user directly from **`http://localhost:5000/admin#tab-overview`**.

### Step 9: Configure ArgoCD Custom Health Check
Patch the `argocd-cm` ConfigMap to enable native health visualization for `TerraformAgent` resources in the ArgoCD UI:
```bash
# Apply health check script patch
kubectl patch configmap argocd-cm -n argocd --patch-file <(python -c "import yaml; from k8s.gitops.argocd_plugin import generate_argocd_cm_patch; print(yaml.dump(generate_argocd_cm_patch()))")
```

### Step 10: Create Your First Declarative Agent Resource
Create an agent manifest `agent.yaml`:
```yaml
apiVersion: platform.terraform-ai.io/v1alpha1
kind: TerraformAgent
metadata:
  name: prod-vpc-fleet
  namespace: default
spec:
  prompt: "Highly available multi-AZ VPC with public and private subnets on AWS"
  engine: opentofu
  environment: production
  governance:
    maxBudgetMonthlyUSD: 500.0
    compliancePack: cis_aws_foundations
    riskThreshold: LOW
  gitops:
    targetRepo: "https://github.com/my-org/cloud-infra.git"
    targetBranch: "main"
    autoHealDrift: true
    createPullRequest: true
  stateBackend:
    provider: s3
    stateBucket: "my-org-terraform-states"
    lockTable: "my-org-terraform-locks"
    region: "us-east-1"
```

Apply and inspect the resource:
```bash
# Apply declarative manifest
kubectl apply -f agent.yaml

# Check lifecycle phase, risk score, and monthly cost
kubectl get terraformagents

# Inspect reconciliation conditions and K8s events
kubectl describe terraformagent prod-vpc-fleet
```

---

## 🩺 Troubleshooting & Frequently Asked Questions (FAQ)

### 1. 🟣 Terraform / 🧅 OpenTofu Binary Missing on PATH
* **Symptom**: `FileNotFoundError: 'terraform' / 'tofu' executable not found on PATH.`
* **Solution**:
  - Windows: Run `winget install HashiCorp.Terraform` or `winget install LinuxFoundation.OpenTofu`, then restart your terminal.
  - Linux / macOS: Install via package manager (`brew install opentofu` or `apt install terraform`).
  - Fallback: The platform automatically verifies binary availability upon boot. You can switch between engines on the Web Dashboard Build tab or via `.env` (`DEFAULT_IAC_ENGINE=terraform` or `DEFAULT_IAC_ENGINE=opentofu`).

### 2. ⚡ Redis Connection Refused / Task Queue Fallback
* **Symptom**: `redis.exceptions.ConnectionError: Error 10061 connecting to localhost:6379.`
* **Solution**:
  - The dashboard automatically detects when Redis is offline and logs: `[Dashboard] Redis is not reachable. Falling back to synchronous thread execution.`
  - To enable asynchronous Celery workers, start Redis via Docker: `docker run -d -p 6379:6379 --name terraform-redis redis:7-alpine`.

### 3. 🐘 PostgreSQL & `pgvector` Initialization
* **Symptom**: `relation "pattern_memory" does not exist` or `extension "vector" is not available.`
* **Solution**:
  - If running in Docker: `docker-compose.yml` uses `pgvector/pgvector:pg15`, which has the `vector` extension pre-installed.
  - If running in Local Python (SQLite): The platform automatically uses an in-memory dense vector cosine similarity engine with zero configuration required.

### 4. 🔀 GitHub Token (PAT) & GitOps PR Permissions
* **Symptom**: `GitHub API 403 / 401 Bad credentials` or `Resource not accessible by personal access token`.
* **Solution**:
  - Ensure your GitHub Personal Access Token (PAT) has the following scopes enabled:
    - `repo` (Full control of private repositories)
    - `workflow` (Update GitHub Action workflows)
    - `read:org` (Read organization data)
  - Verify that the target repository URL in the GitOps form ends with `.git` and is accessible by your account.

### 5. 🐳 Docker Socket Permissions (`/var/run/docker.sock`)
* **Symptom**: `permission denied while trying to connect to the Docker daemon socket.`
* **Solution**:
  - Linux / WSL2: Add your current user to the docker group: `sudo usermod -aG docker $USER` and log back in.
  - Docker Compose: Ensure the volume mount `- /var/run/docker.sock:/var/run/docker.sock` is present in `docker-compose.yml`.

### 6. 🤖 LLM Rate Limits (HTTP 429 / Quota Exhausted)
* **Symptom**: `Rate limit reached for model gemini-3.1-flash-lite (429 Too Many Requests).`
* **Solution**:
  - The agent orchestrator has a built-in exponential backoff retry loop with automatic jitter that pauses and retries failed tasks.
  - You can configure custom BYOK API keys or switch providers in `.env` (Google Gemini, ZenMux AI, OpenAI, Anthropic Claude, Groq, Mistral, OpenRouter).

### 7. 🔐 Enterprise SSO & Identity Provider Redirects
* **Symptom**: `Redirect URI mismatch` or `Invalid OAuth2 state parameter.`
* **Solution**:
  - In your IdP portal (Microsoft Entra ID, Okta, Google Cloud Console, Auth0), register `http://localhost:5000/api/auth/sso/callback` (or your domain callback URL) under **Allowed Redirect URIs**.
  - In local development mode, simulated SSO auto-provisioning is supported out of the box.

### 8. 🛡️ Open Policy Agent (OPA) Evaluation & Rego Packs
* **Symptom**: `Compliance pack 'custom' not found` or `OPA CLI binary not found.`
* **Solution**:
  - The platform includes pure-Python AST evaluation fallbacks for all pre-packaged rulepacks (**SOC2**, **HIPAA**, **PCI-DSS**, **CIS Benchmarks**).
  - To install the native OPA CLI on Windows: `choco install opa -y` or download from [openpolicyagent.org](https://www.openpolicyagent.org/).

### 9. 🆘 Multi-Region Disaster Recovery & Regional Failover
* **Symptom**: `Secondary DR region credentials missing or unauthorized.`
* **Solution**:
  - Ensure cloud credentials (AWS IAM role / Service Principal) have permissions across both primary (`us-east-1`) and secondary DR regions (`us-west-2`).
  - Cross-region state replication snapshots are saved automatically in PostgreSQL / SQLite and verified prior to cutover.

### 10. ☸️ Kubernetes CRD Installation & RBAC Permissions
* **Symptom**: `error: unable to recognize "k8s/crds/...": no matches for kind "CustomResourceDefinition"` or `403 Forbidden on customresourcedefinitions.apiextensions.k8s.io`.
* **Solution**:
  - Ensure your target Kubernetes cluster is version v1.24+ supporting the GA `apiextensions.k8s.io/v1` API.
  - Applying Custom Resource Definitions requires `cluster-admin` privileges. Ensure your `kubeconfig` context has permissions to create cluster-level resources (`ClusterRole`, `CustomResourceDefinition`).
  - To test locally, use KinD (`kind create cluster`) or Minikube (`minikube start`) where your user context has full administrative access.

### 11. 🔌 Port 5000 Collision & Dual-Stack IPv4/IPv6 Docker Binding
* **Symptom**: Logging in at `http://localhost:5000/login` fails with `"Invalid credentials"` even though `scripts/create_admin.py` or user registration reported success, or visiting `/admin` returns 403 or stale data.
* **Cause**: On Windows, when Docker Desktop / WSL2 is running a container (e.g. `terraform-dashboard`) mapped to port 5000, `wslrelay.exe` or `com.docker.backend.exe` binds to IPv6 `::1:5000`. Browsers resolving `localhost` route traffic to the container instead of the local Python host server on `127.0.0.1:5000`.
* **Solution**:
  1. Stop the conflicting Docker container:
     ```powershell
     docker stop terraform-dashboard
     ```
  2. Alternatively, access your local development server explicitly via IPv4:
     **`http://127.0.0.1:5000`** instead of `http://localhost:5000`.
  3. Verify port listeners in PowerShell:
     ```powershell
     Get-NetTCPConnection -LocalPort 5000 | Select-Object LocalAddress, LocalPort, State, OwningProcess
     ```

### 12. 📈 Prometheus Scraping Failure / Target Down on `/metrics`
* **Symptom**: Prometheus targets page (`http://localhost:9090/targets`) shows `terraform-ai-dashboard` as `DOWN` with connection refused or timeout.
* **Solution**:
  - In Kubernetes, ensure the Prometheus ConfigMap targets the Kubernetes service DNS: `terraform-ai-dashboard.terraform-ai-system.svc.cluster.local:5000`.
  - Verify that `/metrics` is unauthenticated and responding: `kubectl exec -n terraform-ai-system prometheus-xxx -- wget -qO- http://terraform-ai-dashboard:5000/metrics`.

### 13. 🛡️ Super-Admin Access Denied (HTTP 403)
* **Symptom**: Accessing `/admin` redirects to login or displays an error: `"Superuser access required"`.
* **Solution**:
  - Verify that the authenticated user has `is_superuser = True` in the database.
  - Run `python scripts/create_admin.py --username <your_username> --promote` to grant super-admin privileges to an existing user without changing their password.

### 14. 📋 Kubernetes Pod Log Streaming Returns Empty
* **Symptom**: In the Super-Admin K8s Control Plane, clicking **Logs** on a pod displays an empty modal or `"No log output available"`.
* **Solution**:
  - Verify that the dashboard ServiceAccount has `get`, `list`, `watch` permissions on `pods/log` across the `terraform-ai-system` namespace.
  - In local development, ensure your local `kubectl` context points to the active cluster: `kubectl config current-context`.

---
*Last Updated: 2026-09-19 (Super-Admin Platform Operations Command Center & Observability Release)*

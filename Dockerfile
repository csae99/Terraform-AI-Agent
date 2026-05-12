# ============================================
# Terraform AI Agent - Multi-Stage Dockerfile
# ============================================
# Bundles: Python 3.11, Terraform, Infracost, Checkov, tfsec
# Usage:
#   docker build -t terraform-ai-agent .
#   docker run --rm -it --env-file .env -v $(pwd)/output:/app/output terraform-ai-agent "create an s3 bucket"

FROM python:3.11-slim AS base

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    git \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------------------
# Install Terraform CLI
# -------------------------------------------
ARG TERRAFORM_VERSION=1.9.8
RUN curl -fsSL https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip -d /usr/local/bin/ \
    && rm terraform.zip \
    && terraform version

# -------------------------------------------
# Install Infracost CLI
# -------------------------------------------
RUN curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh \
    && infracost --version

# -------------------------------------------
# Install tfsec
# -------------------------------------------
ARG TFSEC_VERSION=1.28.11
RUN curl -fsSL -o /usr/local/bin/tfsec https://github.com/aquasecurity/tfsec/releases/download/v${TFSEC_VERSION}/tfsec-linux-amd64 \
    && chmod +x /usr/local/bin/tfsec \
    && tfsec --version

# -------------------------------------------
# Install Azure CLI
# -------------------------------------------
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && az --version

# -------------------------------------------
# Install Google Cloud SDK
# -------------------------------------------
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update -y && apt-get install google-cloud-sdk -y \
    && gcloud --version


# -------------------------------------------
# Set up application
# -------------------------------------------
WORKDIR /app

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Checkov as a pip package (avoids Docker-in-Docker)
RUN pip install --no-cache-dir checkov

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output

# -------------------------------------------
# Entrypoint & Ports
# -------------------------------------------
EXPOSE 5000

# CLI mode (default)
ENTRYPOINT ["python", "app/main.py"]
CMD ["--help"]

# For Dashboard mode:
# docker run -p 5000:5000 --env-file .env -v $(pwd)/output:/app/output --entrypoint python terraform-ai-agent app/dashboard.py


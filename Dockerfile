# ============================================
# Terraform AI Agent - Multi-Stage Dockerfile
# ============================================
# Stage 1: Tool Builder (Fetches & extracts standalone CLI binaries)
# --------------------------------------------
FROM debian:bookworm-slim AS binary-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /out/bin

# 1. Terraform CLI
ARG TERRAFORM_VERSION=1.9.8
RUN curl --http1.1 -fsSL --retry 5 --connect-timeout 20 https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip -o terraform.zip \
    && unzip -q terraform.zip -d /out/bin/ \
    && rm -f terraform.zip

# 2. OpenTofu CLI (for multi-engine support)
ARG OPENTOFU_VERSION=1.8.4
RUN (curl --http1.1 -fsSL --retry 3 --connect-timeout 20 -H "Accept: application/octet-stream" \
        https://api.github.com/repos/opentofu/opentofu/releases/assets/201241219 -o tofu.zip \
     || curl --http1.1 -fsSL --retry 5 --connect-timeout 30 \
        https://github.com/opentofu/opentofu/releases/download/v${OPENTOFU_VERSION}/tofu_${OPENTOFU_VERSION}_linux_amd64.zip -o tofu.zip) \
    && unzip -q tofu.zip -d /out/bin/ \
    && rm -f tofu.zip

# 3. tfsec CLI
ARG TFSEC_VERSION=1.28.11
RUN (curl --http1.1 -fsSL --retry 3 --connect-timeout 20 -H "Accept: application/octet-stream" \
        https://api.github.com/repos/aquasecurity/tfsec/releases/assets/196696010 -o /out/bin/tfsec \
     || curl --http1.1 -fsSL --retry 5 --connect-timeout 30 \
        https://github.com/aquasecurity/tfsec/releases/download/v${TFSEC_VERSION}/tfsec-linux-amd64 -o /out/bin/tfsec) \
    && chmod +x /out/bin/tfsec

# 4. Infracost CLI
RUN curl --http1.1 -fsSL --retry 5 --connect-timeout 20 https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh \
    && cp /usr/local/bin/infracost /out/bin/

# --------------------------------------------
# Stage 2: Final Runtime Image
# --------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_PLUGIN_CACHE_DIR=/tmp/terraform-plugin-cache

# Install runtime dependencies + Cloud CLIs (AWS CLI v2, Azure CLI, Google Cloud CLI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    gnupg \
    unzip \
    groff \
    less \
    ca-certificates \
    && mkdir -p /etc/apt/keyrings \
    # Google Cloud CLI repository
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" \
       | tee /etc/apt/sources.list.d/google-cloud-sdk.list \
    # Install Azure CLI + Google Cloud CLI
    && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-cloud-cli \
    # Install AWS CLI v2
    && curl --http1.1 -fsSL --retry 5 --connect-timeout 30 "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip -q awscliv2.zip \
    && ./aws/install \
    && rm -rf aws awscliv2.zip \
    # Clean up APT caches
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Copy standalone binaries from builder stage
COPY --from=binary-builder /out/bin/ /usr/local/bin/

# Verify installed tools
RUN terraform version \
    && tofu version \
    && tfsec --version \
    && infracost --version \
    && aws --version \
    && az --version \
    && gcloud --version

# Set up application workspace and shared plugin cache
WORKDIR /app
RUN mkdir -p /app/output /tmp/terraform-plugin-cache && chmod 777 /tmp/terraform-plugin-cache

# Install Python dependencies (cached layer)
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt checkov

# Copy application source code (selective copying ensures zero artifact/bloat leakage)
COPY agents/ ./agents/
COPY aiops/ ./aiops/
COPY app/ ./app/
COPY billing/ ./billing/
COPY cloud_optimizer/ ./cloud_optimizer/
COPY consensus/ ./consensus/
COPY crews/ ./crews/
COPY dr/ ./dr/
COPY evaluation/ ./evaluation/
COPY k8s/ ./k8s/
COPY llm/ ./llm/
COPY marketplace/ ./marketplace/
COPY memory/ ./memory/
COPY observability/ ./observability/
COPY optimization/ ./optimization/
COPY orchestrator/ ./orchestrator/
COPY policy/ ./policy/
COPY portal/ ./portal/
COPY scripts/ ./scripts/
COPY sso/ ./sso/
COPY static/ ./static/
COPY test-cases/ ./test-cases/
COPY tools/ ./tools/
COPY workers/ ./workers/
COPY workflows/ ./workflows/

EXPOSE 5000

# Default entrypoint (CLI mode)
ENTRYPOINT ["python", "app/main.py"]
CMD ["--help"]


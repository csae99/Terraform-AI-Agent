# Terraform AI Agent - Bug Fixes & Agent Hardening

We've successfully stabilized the agent orchestration pipeline and strengthened the LLM prompts to eliminate the persistent hallucinations and syntax errors. 

## What We Fixed

1. **HCL Semicolon Eradication** 
   - *Problem:* The LLMs (especially smaller ones like Gemini Flash Lite) frequently attempted to compress HCL blocks onto a single line by separating arguments with semicolons (e.g., `vpc_id = x; cidr_block = y`), which is strictly forbidden in Terraform.
   - *Fix:* Implemented `_sanitize_hcl()` in the `TerraformTools` class to dynamically intercept file writes, replace semicolons with newlines, and ensure closing braces are on their own line. We also added an automatic `terraform fmt` pass.

2. **Incomplete EKS Topologies**
   - *Problem:* AWS EKS strictly requires at least 2 subnets across 2 different Availability Zones, and specific IAM policy attachments (like `AmazonEKSWorkerNodePolicy`). The agents kept missing these.
   - *Fix:* Explicitly embedded an "EKS COMPLETENESS CHECKLIST" directly into both the Architect and Developer system prompts.

3. **Validation Pre-initialization Error**
   - *Problem:* `terraform validate` was failing because modules were not installed.
   - *Fix:* Ensure `terraform init -backend=false` runs before validation.

4. **"Lazy" Developer Agent (LiteLLM Issue)**
   - *Problem:* When using `gemini/gemini-3.1-flash-lite`, the model would "complete" the task by just outputting text, failing to actually trigger the `write_terraform_file` tool for the 15+ module files.
   - *Fix:* Rewrote the `TerraformDeveloper` system prompt to strictly enforce tool usage for *every single file*. We also increased `max_iter` to 30 to give the model enough headroom to make 16+ sequential JSON tool calls.

## Verification

We performed an end-to-end test using the `gemini-3.1-flash-lite` model with the highly complex EKS prompt.
- **Architect Phase:** Successfully generated the Mermaid design and mandated multi-AZ subnets.
- **Developer Phase:** The agent successfully made **16 consecutive tool calls**, writing the root files and creating the full `vpc`, `iam`, `eks`, and `security_groups` module directories.
- **Audit Phase:** `terraform validate` passed on the first try! No syntax errors.
- **FinOps Phase:** Properly detected the high cost ($1,198/month) of the requested `m5.4xlarge` nodes and correctly flagged the workspace as "OVER BUDGET".

The multi-agent Terraform pipeline is now fully resilient to LLM formatting hallucinations and can execute complex, multi-module infrastructure generation using smaller, faster Lite models!

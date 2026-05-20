from crewai import Task

class TerraformGenerationTasks:

    @staticmethod
    def design_architecture_task(agent, requirement):
        return Task(
            description=f'Analyze the following infrastructure requirement and design a MINIMAL architecture.\n'
                        f'Requirement: {requirement}\n'
                        'IMPORTANT: DO NOT add NAT Gateways, Private Subnets, or Multi-AZ unless explicitly requested.\n'
                        '1. Identify necessary providers and resources.\n'
                        '2. You MUST provide a **Mermaid.js diagram string** representing the architecture.\n'
                        '3. The first line of your response must be: PROJECT_SLUG: <slug>\n'
                        '   - The slug MUST be a descriptive kebab-case name derived from the requirement (e.g., "eks-public-cluster", "s3-versioned-bucket").\n'
                        '   - NEVER use generic names like "terraform-project" or timestamps.\n'
                        '\n'
                        'EKS-SPECIFIC RULES:\n'
                        '- If creating EKS, ALWAYS include at least 2 public subnets in 2 different AZs (EKS requires this).\n'
                        '- ALWAYS include IAM policy attachments (AmazonEKSClusterPolicy, AmazonEKSWorkerNodePolicy, AmazonEC2ContainerRegistryReadOnly, AmazonEKS_CNI_Policy).\n'
                        '- ALWAYS include security groups for the cluster and nodes.\n'
                        '- The design MUST include a `provider` block and `terraform { required_providers { } }` block.\n',
            expected_output='A detailed architecture document including a Mermaid.js diagram block starting with ```mermaid. The first line must be: PROJECT_SLUG: <slug>',
            agent=agent
        )

    @staticmethod
    def write_terraform_task(agent, project_slug, arch_result, error_guidance=""):
        desc = (
            f'Based on the Architect\'s design, implement the Terraform project: {project_slug}.\n'
            f'--- ARCHITECTURE DESIGN ---\n{arch_result}\n---------------------------\n'
        )
        if error_guidance:
            desc += (
                f'\n\n⚠️--- ATTENTION: PREVIOUS ROUND FAILED ---\n'
                f'Please correct the following errors and apply this advice in the new configuration:\n'
                f'{error_guidance}\n'
                f'-------------------------------------------\n\n'
            )
        
        desc += (
            '\n'
            '## MANDATORY RULES (FAILURE TO FOLLOW = BROKEN CODE)\n'
            '1. You MUST use the `Write Terraform File` tool for EVERY SINGLE FILE you create.\n'
            '2. DO NOT WRITE PLAIN TEXT TERRAFORM. YOU MUST CALL THE TOOL.\n'
            '3. If you need to create 15 files, you MUST call the tool 15 times.\n'
            '4. Structure: Root `main.tf` calling modules in `modules/` directory.\n'
            '   Module sources MUST be relative path strings (e.g., source = "./modules/vpc").\n'
            '5. You MUST create a `README.md` in the project ROOT.\n'
            '\n'
            '## HCL FORMATTING (CRITICAL)\n'
            '- NEVER use semicolons (;) to separate arguments. Use NEWLINES.\n'
            '- Every resource argument MUST be on its own line.\n'
            '- Every closing brace } MUST be on its own line.\n'
            '- BAD:  resource "aws_subnet" "s1" { vpc_id = aws_vpc.main.id; cidr_block = "10.0.1.0/24" }\n'
            '- GOOD:\n'
            '  resource "aws_subnet" "s1" {\n'
            '    vpc_id     = aws_vpc.main.id\n'
            '    cidr_block = "10.0.1.0/24"\n'
            '  }\n'
            '\n'
            '## REQUIRED FILES\n'
            '- Root `main.tf`: Must include a `terraform { required_providers { } }` block and a `provider` block.\n'
            '- Root `variables.tf`: Input variables (e.g., region).\n'
            '- Root `outputs.tf`: Key outputs (endpoints, IDs, ARNs).\n'
            '\n'
            '## EKS / INFRASTRUCTURE COMPLETENESS CHECKLIST\n'
            'If creating EKS, you MUST include ALL of the following:\n'
            '- At least 2 subnets across 2 different Availability Zones (EKS requires this).\n'
            '- Subnets must have `map_public_ip_on_launch = true` for public clusters.\n'
            '- IAM roles MUST have `aws_iam_role_policy_attachment` resources:\n'
            '  * Cluster role: AmazonEKSClusterPolicy\n'
            '  * Node role: AmazonEKSWorkerNodePolicy, AmazonEC2ContainerRegistryReadOnly, AmazonEKS_CNI_Policy\n'
            '- EKS `vpc_config` must include `endpoint_public_access = true` for public clusters.\n'
            '- Node group must have `depends_on` referencing the IAM policy attachments.\n'
            '- Subnets should be tagged: `kubernetes.io/cluster/<name> = shared`.\n'
            '\n'
            f'Project Slug: {project_slug}'
        )

        return Task(
            description=desc,
            expected_output=f'A fully populated modular project in output/{project_slug}/ consisting of multiple .tf files.',
            agent=agent
        )

"""
Pipeline – central orchestrator for the multi-agent workflow.

Extracted from app/main.py so that both the CLI entry-point and the
Flask dashboard can invoke the same deterministic pipeline.
"""

import os
import re
from datetime import datetime

from crewai import Crew, Process

from agents.terraform_architect import TerraformArchitect
from agents.terraform_developer import TerraformDeveloper
from agents.security_reviewer import SecurityReviewer
from agents.cost_optimizer import CostOptimizer
from agents.deployment_planner import DeploymentPlanner
from agents.testing_agent import TestingAgent

from workflows.terraform_generation import TerraformGenerationTasks
from workflows.terraform_validation import TerraformValidationTasks
from workflows.terraform_deployment import TerraformDeploymentTasks
from workflows.terraform_testing import TerraformTestingTasks

from tools.security.scanning_tools import SecurityAuditor
from tools.finance.cost_estimation import CostEstimator
from tools.cloud.aws_tools import CloudSync
from tools.terraform.terraform_tools import TerraformTools
from tools.project.tracker import ProjectTracker

from orchestrator.retry_handler import RetryContext, should_retry, _get_pattern_manager


# ── Helper utilities ─────────────────────────────────────────────────

import uuid
import re

def get_project_slug(architect_output: str, prompt: str = "") -> str:
    """Extract a URL-friendly slug from the architect's output."""
    # Handle possible markdown bolding, spaces/underscores, and case insensitivity
    match = re.search(r"\*?\*?project[_\s]slug\*?\*?:?\*?\*?\s*([^\n\r]+)", architect_output, re.IGNORECASE)
    if match:
        name = match.group(1).replace("*", "").strip()
        slug = name.lower().replace(" ", "-").replace("_", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        if slug:
            return slug
    
    # Fallback: extract the first 3 meaningful words from the prompt
    if prompt:
        generic = {"create", "make", "build", "generate", "terraform", "configuration", "infrastructure", "production", "valid", "code", "the", "a", "an", "for", "with", "using", "setup", "deploy", "provision"}
        words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', prompt).lower().split() if len(w) > 2 and w not in generic]
        if words:
            return "-".join(words[:3])
            
    # Ultimate fallback if LLM completely failed and no prompt
    short_id = str(uuid.uuid4())[:8]
    return f"aws-infrastructure-{short_id}"


def extract_mermaid(text: str) -> str:
    """Extract mermaid code block from text."""
    pattern = r"```mermaid\s+(.*?)\s+```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def inject_floci_overrides(slug: str):
    """Write a providers_override.tf file to force Terraform to use local Floci emulated endpoints."""
    output_base = os.path.join("output", slug)
    if not os.path.exists(output_base):
        os.makedirs(output_base)
        
    is_in_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER") == "true"
    floci_host = "floci" if is_in_docker else "localhost"
    floci_endpoint = f"http://{floci_host}:4566"
    
    override_content = f"""
provider "aws" {{
  region                      = "us-east-1"
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true
  endpoints {{
    apigateway     = "{floci_endpoint}"
    apigatewayv2   = "{floci_endpoint}"
    autoscaling    = "{floci_endpoint}"
    cloudformation = "{floci_endpoint}"
    cloudfront     = "{floci_endpoint}"
    cloudwatch     = "{floci_endpoint}"
    cognitoidp     = "{floci_endpoint}"
    cognitoidentity= "{floci_endpoint}"
    dynamodb       = "{floci_endpoint}"
    ec2            = "{floci_endpoint}"
    ecs            = "{floci_endpoint}"
    eks            = "{floci_endpoint}"
    elasticsearch  = "{floci_endpoint}"
    firehose       = "{floci_endpoint}"
    iam            = "{floci_endpoint}"
    kinesis        = "{floci_endpoint}"
    kms            = "{floci_endpoint}"
    lambda         = "{floci_endpoint}"
    redshift       = "{floci_endpoint}"
    route53        = "{floci_endpoint}"
    s3             = "{floci_endpoint}"
    secretsmanager = "{floci_endpoint}"
    ses            = "{floci_endpoint}"
    sns            = "{floci_endpoint}"
    sqs            = "{floci_endpoint}"
    ssm            = "{floci_endpoint}"
    stepfunctions  = "{floci_endpoint}"
    sts            = "{floci_endpoint}"
  }}
}}
"""
    override_path = os.path.join(output_base, "providers_override.tf")
    with open(override_path, "w") as f:
        f.write(override_content)
    print(f"[Local Test] Injected Floci overrides at {override_path}")


# ── Main Pipeline ────────────────────────────────────────────────────

def run_full_pipeline(
    prompt: str,
    budget: float = 100.0,
    do_apply: bool = False,
    auto_fix: bool = False,
    model_name: str = None,
    model_key: str = None,
    owner_id: str = None,
    new_project: bool = False,
    cli_flags: list = None,
    test_local: bool = False,
) -> dict:
    """Execute the full multi-agent Terraform pipeline.

    This is the single authoritative entry-point for both the CLI
    (``app/main.py``) and the web dashboard (``app/dashboard.py``).

    Returns:
        dict with keys: slug, status, estimated_cost, security_issues
    """
    is_test_local = test_local or os.environ.get("TEST_LOCAL") == "true" or "--test-local" in (cli_flags or [])

    if cli_flags is None:
        cli_flags = []

    print("\n" + "=" * 50)
    print("      Universal AI Agent - Phase 7 (Visualizer Platform)")
    print("=" * 50 + "\n")

    # ── Instantiate agent classes ────────────────────────────────
    architect_agent_cls = TerraformArchitect(model_name=model_name, api_key=model_key)
    developer_agent_cls = TerraformDeveloper(model_name=model_name, api_key=model_key)
    auditor_agent_cls = SecurityReviewer(model_name=model_name, api_key=model_key)
    finops_agent_cls = CostOptimizer(model_name=model_name, api_key=model_key)
    deployer_agent_cls = DeploymentPlanner(model_name=model_name, api_key=model_key)
    testing_agent_cls = TestingAgent(model_name=model_name, api_key=model_key)

    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()

    # ── 1. Cloud Readiness & Architecture ────────────────────────
    readiness = cloud.check_cloud_readiness()
    detected_provider = readiness["provider"]
    print(f"Cloud Readiness: {detected_provider} Ready")

    architect_agent = architect_agent_cls.get_agent()
    arch_task = TerraformGenerationTasks.design_architecture_task(architect_agent, prompt)

    crew_arch = Crew(agents=[architect_agent], tasks=[arch_task], verbose=True)
    arch_result = str(crew_arch.kickoff())

    slug = get_project_slug(arch_result, prompt)
    base_slug = slug
    if new_project:
        counter = 1
        while ProjectTracker.load(slug) is not None or os.path.exists(os.path.join("output", slug)):
            slug = f"{base_slug}-{counter}"
            counter += 1
    # Replace references to the base slug in the architecture design document with the actual slug
    if slug != base_slug:
        arch_result = re.sub(re.escape(base_slug), slug, arch_result, flags=re.IGNORECASE)
    mermaid_diagram = extract_mermaid(arch_result)
    output_base = os.path.join("output", slug)
    print(f"\nBuilding Project Workspace: {output_base}/")

    # ── Track project from the start ─────────────────────────────
    ProjectTracker.save(
        slug,
        prompt=prompt,
        status="generating",
        budget=budget,
        provider=detected_provider,
        flags=cli_flags,
        mermaid_diagram=mermaid_diagram,
        owner_id=owner_id,
    )

    # ── 2. Development & Audit Loop (self-healing) ───────────────
    retry = RetryContext(max_rounds=3)
    is_deployed = False

    while retry.has_retries_left:
        print(f"\n--- Round {retry.current_round}: Development & Audit ---")

        developer_agent = developer_agent_cls.get_agent()
        auditor_agent = auditor_agent_cls.get_agent()
        finops_agent = finops_agent_cls.get_agent()
        deployer_agent = deployer_agent_cls.get_agent()
        testing_agent = testing_agent_cls.get_agent()

        # Check if we have previous errors/advice to inject
        error_guidance = ""
        if retry.current_round > 1 and retry.errors:
            latest_error = retry.errors[-1]
            error_guidance = TerraformValidationTasks.build_error_context(latest_error)
            if retry.advice:
                error_guidance += f"\nAdvice from pattern memory:\n{retry.advice}"

        dev_task = TerraformGenerationTasks.write_terraform_task(
            developer_agent, slug, arch_result, error_guidance=error_guidance
        )
        audit_task = TerraformValidationTasks.audit_task(auditor_agent, slug)
        cost_task = TerraformValidationTasks.financial_analysis_task(
            finops_agent, slug, budget
        )
        deploy_task = (
            TerraformDeploymentTasks.deployment_task(deployer_agent, slug)
            if do_apply
            else None
        )
        testing_task = (
            TerraformTestingTasks.behavior_testing_task(testing_agent, slug)
            if do_apply
            else None
        )

        active_tasks = [dev_task, audit_task, cost_task]
        active_agents = [developer_agent, auditor_agent, finops_agent]

        if deploy_task:
            active_tasks.append(deploy_task)
            active_agents.append(deployer_agent)

        if testing_task:
            active_tasks.append(testing_task)
            active_agents.append(testing_agent)

        crew_dev = Crew(
            agents=active_agents,
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True,
        )

        try:
            crew_result = str(crew_dev.kickoff())
        except Exception as e:
            print(f"\n[!] Developer Crew failed with error: {str(e)}")
            ProjectTracker.update_status(slug, "failed")
            return {
                "slug": slug,
                "status": "failed",
                "estimated_cost": "0.00",
                "security_issues": 0,
            }

        if is_test_local:
            inject_floci_overrides(slug)

        # ── Security analysis for self-healing ───────────────────
        audit_results = auditor.run_comprehensive_scan(output_base)
        
        # Ensure terraform is syntactically valid before considering this round a success
        val_result = TerraformTools._validate_terraform_code(slug)
        if "Failed" in val_result:
            if should_retry(val_result):
                print(f"\n[!] Terraform Validation Failed. Retrying...")
                retry.record_errors(f"Terraform validation failed: {val_result}")
                retry.advance()
                continue
            else:
                print("\n[!] Hard stop or max retries reached. Validation failed.")
                retry.record_errors(f"Terraform validation failed (hard stop): {val_result}")
                break
                
        findings = audit_results.get("findings", [])
        critical_count = len(
            [f for f in findings if f.get("severity") in ["CRITICAL", "HIGH"]]
        )

        # Track best state
        if retry.best_finding_count is None or critical_count < retry.best_finding_count:
            retry.best_finding_count = critical_count
            backup_result = TerraformTools._backup_workspace(slug)
            if "Backup created at " in backup_result:
                retry.best_backup = backup_result.split("Backup created at ")[1].strip()
                print(
                    f"  📸 Snapshot saved (best so far: {retry.best_finding_count} issues)"
                )

        # Check deployment success
        is_deployed = True
        if do_apply:
            if deploy_task and hasattr(deploy_task, "output") and deploy_task.output:
                is_deployed = "🚀 Deployment Successful!" in str(deploy_task.output.raw)
            else:
                log_path = os.path.join(output_base, "logs", "terraform_apply.log")
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8") as f:
                            apply_log = f.read()
                        is_deployed = "Apply complete!" in apply_log
                    except Exception as e:
                        print(f"[Deployment Check] Warning: failed to read apply log: {e}")
                        is_deployed = False
                else:
                    is_deployed = False

        if critical_count == 0 and is_deployed:
            print(
                "\n✅ Verification SUCCESS! No security issues and deployment is live."
            )
            if retry.current_round > 1:
                main_tf_path = os.path.join(output_base, "main.tf")
                fix_applied_content = ""
                if os.path.exists(main_tf_path):
                    try:
                        with open(main_tf_path, "r", encoding="utf-8") as f:
                            fix_applied_content = f.read()
                    except Exception as e:
                        print(f"[Self-Learning] Warning: failed to read {main_tf_path}: {e}")
                
                pm = _get_pattern_manager()
                if pm:
                    print(f"[Self-Learning] Run succeeded in round {retry.current_round}. Calling pattern_manager.learn_from_run...")
                    pm.learn_from_run(
                        error_logs="\n".join(retry.errors),
                        fix_applied=fix_applied_content
                    )
            break

        # ── Record errors & enrich with pattern advice ───────────
        error_summary = ""
        if critical_count > 0:
            error_summary += f"Security audit failed:\n{auditor.format_report(audit_results)}\n"
        if not is_deployed:
            error_summary += f"Deployment failed. Raw output:\n{crew_result}\n"
        
        if not error_summary:
            error_summary = f"Round {retry.current_round}: Verification failed for unknown reasons."

        retry.record_errors(error_summary)

        if retry.current_round < retry.max_rounds:
            if auto_fix:
                print(
                    f"\n🤖 Auto-Fix Enabled: Proceeding to Round {retry.current_round + 1}..."
                )
            else:
                choice = input(
                    f"\nWould you like to proceed with autonomous Fix Round "
                    f"{retry.current_round + 1}? [y/n]: "
                ).lower()
                if choice != "y":
                    break

            retry.advance()
        else:
            print("\n❌ Max rounds reached.")
            break

    # ── 3. Revert Logic ──────────────────────────────────────────
    if (
        retry.best_finding_count
        and retry.best_finding_count > 0
        and retry.best_backup
    ):
        print(
            f"\n[WARNING] Project has {retry.best_finding_count} unresolved high-severity issues."
        )
        if auto_fix:
            print("🤖 Auto-Fix Enabled: Automatically reverting to best-known state.")
            revert_choice = "y"
        else:
            revert_choice = input(
                "Would you like to REVERT to the best-known state? (Recommended) [y/n]: "
            ).lower()

        if revert_choice == "y":
            TerraformTools._restore_workspace(slug, retry.best_backup)
            print(
                f"Workspace reverted to best-known version with "
                f"{retry.best_finding_count} issues."
            )

    # ── 4. Final FinOps Report ───────────────────────────────────
    print("\nFinalizing Project Reports...")
    cost_results = estimator._execute_infracost(output_base)

    total_cost = float(cost_results.get("total_monthly_cost", 0))
    budget_status = (
        "✅ WITHIN BUDGET" if total_cost <= budget else "❌ OVER BUDGET"
    )

    final_status = "deployed" if (do_apply and is_deployed) else "generated"
    final_security = (
        retry.best_finding_count if retry.best_finding_count is not None else 0
    )

    ProjectTracker.save(
        slug,
        prompt=prompt,
        status=final_status,
        budget=budget,
        estimated_cost=total_cost,
        security_issues=final_security,
        provider=detected_provider,
        flags=cli_flags,
        mermaid_diagram=mermaid_diagram,
        owner_id=owner_id,
    )

    print("\n" + "=" * 50)
    print("                FINAL AGENT REPORTS")
    print("=" * 50)
    print(f"BUDGET STATUS: {budget_status} (Limit: ${budget})")
    print(estimator.format_report(cost_results))
    print("=" * 50)

    print(f"\nWorkflow complete! Final output at: output/{slug}/")
    print("📊 Dashboard: python dashboard.py  →  http://localhost:5000")

    return {
        "slug": slug,
        "status": final_status,
        "estimated_cost": total_cost,
        "security_issues": final_security,
    }


# ── Destroy helper ───────────────────────────────────────────────────

def run_destroy_pipeline(slug: str, model_name: str = None, model_key: str = None):
    """Destroy an existing workspace."""
    print(f"\n☢️  DESTRUCTIVE ACTION: Destroying workspace '{slug}'")
    decom_agent_cls = DeploymentPlanner(model_name=model_name, api_key=model_key)
    decom_agent = decom_agent_cls.get_agent()
    decom_task = TerraformDeploymentTasks.decommissioning_task(decom_agent, slug)
    crew_decom = Crew(agents=[decom_agent], tasks=[decom_task], verbose=True)
    crew_decom.kickoff()
    ProjectTracker.save(slug, status="destroyed")
    print(f"\n✅ Infrastructure Destroyed for {slug}")

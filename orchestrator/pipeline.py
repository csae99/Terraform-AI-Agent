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

from workflows.terraform_generation import TerraformGenerationTasks
from workflows.terraform_validation import TerraformValidationTasks
from workflows.terraform_deployment import TerraformDeploymentTasks

from tools.security.scanning_tools import SecurityAuditor
from tools.finance.cost_estimation import CostEstimator
from tools.cloud.aws_tools import CloudSync
from tools.terraform.terraform_tools import TerraformTools
from tools.project.tracker import ProjectTracker

from orchestrator.retry_handler import RetryContext, should_retry


# ── Helper utilities ─────────────────────────────────────────────────

def get_project_slug(architect_output: str) -> str:
    """Extract a URL-friendly slug from the architect's output."""
    match = re.search(r"PROJECT_SLUG:\s*(.*)", architect_output)
    if match:
        name = match.group(1).strip()
        slug = name.lower().replace(" ", "-").replace("_", "-")
        return re.sub(r"[^a-z0-9-]", "", slug)
    return "terraform-project-" + datetime.now().strftime("%Y%m%d-%H%M")


def extract_mermaid(text: str) -> str:
    """Extract mermaid code block from text."""
    pattern = r"```mermaid\s+(.*?)\s+```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


# ── Main Pipeline ────────────────────────────────────────────────────

def run_full_pipeline(
    prompt: str,
    budget: float = 100.0,
    do_apply: bool = False,
    auto_fix: bool = False,
    model_name: str = None,
    model_key: str = None,
    owner_id: str = None,
    cli_flags: list = None,
) -> dict:
    """Execute the full multi-agent Terraform pipeline.

    This is the single authoritative entry-point for both the CLI
    (``app/main.py``) and the web dashboard (``app/dashboard.py``).

    Returns:
        dict with keys: slug, status, estimated_cost, security_issues
    """

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

    slug = get_project_slug(arch_result)
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

        dev_task = TerraformGenerationTasks.write_terraform_task(
            developer_agent, slug, arch_result
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

        active_tasks = [dev_task, audit_task, cost_task]
        active_agents = [developer_agent, auditor_agent, finops_agent]

        if deploy_task:
            active_tasks.append(deploy_task)
            active_agents.append(deployer_agent)

        crew_dev = Crew(
            agents=active_agents,
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True,
        )

        crew_result = str(crew_dev.kickoff())

        # ── Security analysis for self-healing ───────────────────
        audit_results = auditor.run_comprehensive_scan(output_base)
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
        is_deployed = "🚀 Deployment Successful!" in crew_result if do_apply else True

        if critical_count == 0 and is_deployed:
            print(
                "\n✅ Verification SUCCESS! No security issues and deployment is live."
            )
            break

        # ── Record errors & enrich with pattern advice ───────────
        error_summary = f"Round {retry.current_round}: {critical_count} critical/high issues."
        if not is_deployed:
            error_summary += " Deployment failed."
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

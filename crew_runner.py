import sys
import io
import os
import re
# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from crewai import Crew, Process, Task
from agents import TerraformAgents
from tasks import TerraformTasks
from tools.security_tools import SecurityAuditor
from tools.financial_tools import CostEstimator
from tools.cloud_tools import CloudSync
from tools.terraform_tools import TerraformTools

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"  # Disables the underlying OpenTelemetry
def get_project_slug(architect_output):
    """Parses PROJECT_SLUG from architect output."""
    match = re.search(r"PROJECT_SLUG:\s*([\w-]+)", architect_output, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "workspace"

import argparse

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Terraform Platform (Phase 5)")
    parser.add_argument("prompt", type=str, nargs="?", help="Your infrastructure requirement")
    parser.add_argument("--budget", type=float, default=100.0, help="Monthly budget limit in USD")
    parser.add_argument("--apply", action="store_true", help="Enable live deployment (Self-Healing)")
    parser.add_argument("--destroy", type=str, help="Destroy an existing workspace (provide slug)")
    args = parser.parse_args()

    agents = TerraformAgents()
    tasks = TerraformTasks()
    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()

    # --- Decommissioning Flow ---
    if args.destroy:
        slug = args.destroy
        print(f"\n⚠️ WARNING: Initiating decommissioning of workspace: {slug}")
        
        deployer_agent = agents.deployment_specialist()
        destroy_task = tasks.decommissioning_task(deployer_agent, slug)
        
        crew = Crew(
            agents=[deployer_agent],
            tasks=[destroy_task],
            verbose=True
        )
        
        result = crew.kickoff()
        print("\n--- Decommissioning Result ---")
        print(result)
        return

    # --- Standard Development Flow ---
    if not args.prompt:
        print("Error: No prompt provided. Usage: python crew_runner.py 'prompt' [--apply]")
        return
    
    requirement = args.prompt
    budget = args.budget
    do_apply = args.apply

    print("\n" + "="*50)
    print("      Universal AI Agent - Phase 5 (Self-Healing Deployment)")
    print("="*50 + "\n")

    # 1. Cloud Readiness & Initial Architect
    readiness = cloud.check_cloud_readiness()
    print(f"Cloud Readiness: {readiness['provider']} Ready")
    
    architect_agent = agents.cloud_architect()
    arch_task = tasks.design_architecture_task(architect_agent, requirement)
    
    crew_arch = Crew(agents=[architect_agent], tasks=[arch_task], verbose=True)
    arch_result = str(crew_arch.kickoff())
    
    slug = get_project_slug(arch_result)
    output_base = os.path.join("output", slug)
    print(f"\nBuilding Project Workspace: {output_base}/")

    # 3. Main Development & Audit Loop
    max_rounds = 3
    current_round = 1
    best_finding_count = 999

    dev_agent = agents.terraform_developer()
    reviewer_agent = agents.security_reviewer()
    finops_agent = agents.finops_specialist()
    deployer_agent = agents.deployment_specialist()

    # Shared context for all agents
    context_text = f"ARCHITECT DESIGN:\n{arch_result}\n\nREQUIRED SLUG: {slug}"

    while current_round <= max_rounds:
        print(f"\n--- [Round {current_round}/{max_rounds}] Starting Agentic Workflow ---")
        
        # Build task list with context
        coding_task = tasks.write_terraform_task(dev_agent, slug)
        coding_task.description += f"\n\nContext:\n{context_text}"
        
        audit_task = tasks.audit_task(reviewer_agent, slug)
        audit_task.description += f"\n\nContext:\n{context_text}"
        
        finops_task = tasks.financial_analysis_task(finops_agent, slug, budget=budget)
        finops_task.description += f"\n\nContext:\n{context_text}"

        workflow_tasks = [coding_task, audit_task, finops_task]

        # Add deployment task if --apply is set
        if do_apply:
            deploy_task = tasks.deployment_task(deployer_agent, slug)
            deploy_task.description += f"\n\nContext:\n{context_text}"
            workflow_tasks.append(deploy_task)

        crew = Crew(
            agents=[dev_agent, reviewer_agent, finops_agent, deployer_agent] if do_apply else [dev_agent, reviewer_agent, finops_agent],
            tasks=workflow_tasks,
            process=Process.sequential,
            verbose=True
        )
        
        crew_result = str(crew.kickoff())
        
        # Comprehensive Security Audit (Ground Truth)
        print("\nVerifying with Deep Security Scan (Checkov)...")
        results = auditor.run_comprehensive_scan(output_base)
        findings = results.get("findings", [])
        critical_count = len([f for f in findings if f["severity"] in ["CRITICAL", "HIGH"]])
        
        # Check for Deployment Success in the result if we attempted apply
        is_deployed = "🚀 Deployment Successful!" in crew_result if do_apply else True

        if critical_count == 0 and is_deployed:
            print("\n✅ Phase 5 Verification SUCCESS! No security issues and deployment is live.")
            break
        
        # SELF-HEALING INTERACTION
        if critical_count > 0:
            print(f"\n⚠️ Security Audit: Found {critical_count} critical/high issues.")
        if do_apply and not is_deployed:
            print(f"\n❌ Deployment Failed. Attempting to heal based on logs...")
        
        if current_round < max_rounds:
            choice = input(f"\nWould you like to proceed with autonomous Fix Round {current_round + 1}? [y/n]: ").lower()
            if choice != 'y':
                break
            current_round += 1
        else:
            print("\n❌ Max rounds reached.")
            break

    # 4. Final Cleanup & Revert Logic
    if best_finding_count > 0:
        print(f"\n[WARNING] Project contains {best_finding_count} unresolved high-severity issues.")
        revert_choice = input(f"Would you like to REVERT the workspace to its best-known state? (Recommended) [y/n]: ").lower()
        if revert_choice == 'y' and best_backup:
            # Extract path from message: "Backup created at output\.backups\..."
            backup_path = best_backup.split("Backup created at ")[1].strip()
            TerraformTools._restore_workspace(slug, backup_path)
            print(f"Workspace reverted to best-known version with {best_finding_count} issues.")

    # 5. Final FinOps Audit & Report
    print("\nFinalizing Project Reports...")
    # The FinOps agent already generated the report in the task, 
    # but we'll fetch a summary for the console.
    cost_results = estimator._execute_infracost(output_base)
    
    # Budget Check Logic
    total_cost = float(cost_results.get("total_monthly_cost", 0))
    budget_status = "✅ WITHIN BUDGET" if total_cost <= budget else "❌ OVER BUDGET"

    print("\n" + "="*50)
    print("                FINAL AGENT REPORTS")
    print("="*50)
    print(f"BUDGET STATUS: {budget_status} (Limit: ${budget})")
    print(estimator.format_report(cost_results))
    print("="*50)

    print(f"\nWorkflow complete! Final output at: output/{slug}/")

if __name__ == "__main__":
    main()

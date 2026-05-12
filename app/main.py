import sys
import io
import os
import re
import argparse
from datetime import datetime

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
from tools.project_tracker import ProjectTracker

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

def get_project_slug(architect_output):
    """Extract a URL-friendly slug from the architect's output."""
    match = re.search(r"PROJECT_SLUG:\s*(.*)", architect_output)
    if match:
        name = match.group(1).strip()
        slug = name.lower().replace(" ", "-").replace("_", "-")
        return re.sub(r"[^a-z0-9-]", "", slug)
    return "terraform-project-" + datetime.now().strftime("%Y%m%d-%H%M")


def extract_mermaid(text):
    """Extract mermaid code block from text."""
    pattern = r"```mermaid\s+(.*?)\s+```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Terraform Platform (Phase 7)")
    parser.add_argument("prompt", type=str, nargs="?", help="Your infrastructure requirement")
    parser.add_argument("--budget", type=float, default=100.0, help="Monthly budget limit in USD")
    parser.add_argument("--apply", action="store_true", help="Enable live deployment (Self-Healing)")
    parser.add_argument("--destroy", type=str, help="Destroy an existing workspace (provide slug)")
    parser.add_argument("--auto-fix", action="store_true", help="Automatically proceed (non-interactive)")
    parser.add_argument("--model", type=str, help="LLM Model to use (e.g. openai/gpt-4o)")
    parser.add_argument("--model-key", type=str, help="API Key for the selected model")
    args = parser.parse_args()

    agents = TerraformAgents(model_name=args.model, api_key=args.model_key)
    tasks = TerraformTasks()
    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()


    # Handle Destructive Actions
    if args.destroy:
        slug = args.destroy
        print(f"\n☢️  DESTRUCTIVE ACTION: Destroying workspace '{slug}'")
        decom_agent = agents.deployment_specialist()
        decom_task = tasks.decommissioning_task(decom_agent, slug)
        crew_decom = Crew(agents=[decom_agent], tasks=[decom_task], verbose=True)
        crew_decom.kickoff()
        ProjectTracker.save(slug, status="destroyed")
        print(f"\n✅ Infrastructure Destroyed for {slug}")
        return

    if not args.prompt:
        parser.print_help()
        return

    requirement = args.prompt
    budget = args.budget
    do_apply = args.apply

    print("\n" + "="*50)
    print("      Universal AI Agent - Phase 7 (Visualizer Platform)")
    print("="*50 + "\n")

    # 1. Cloud Readiness & Initial Architect
    readiness = cloud.check_cloud_readiness()
    detected_provider = readiness['provider']
    print(f"Cloud Readiness: {detected_provider} Ready")
    
    architect_agent = agents.cloud_architect()
    arch_task = tasks.design_architecture_task(architect_agent, requirement)
    
    crew_arch = Crew(agents=[architect_agent], tasks=[arch_task], verbose=True)
    arch_result = str(crew_arch.kickoff())
    
    slug = get_project_slug(arch_result)
    mermaid_diagram = extract_mermaid(arch_result)
    output_base = os.path.join("output", slug)
    print(f"\nBuilding Project Workspace: {output_base}/")

    # Track project from the start
    cli_flags = ["--apply"] if do_apply else []
    if budget != 100.0:
        cli_flags.append(f"--budget={budget}")
    if args.auto_fix:
        cli_flags.append("--auto-fix")

    ProjectTracker.save(slug, prompt=requirement, status="generating",
                        budget=budget, provider=detected_provider, flags=cli_flags,
                        mermaid_diagram=mermaid_diagram)

    # 3. Main Development & Audit Loop
    max_rounds = 3
    current_round = 1
    best_finding_count = None
    best_backup = None

    while current_round <= max_rounds:
        print(f"\n--- Round {current_round}: Deployment & Audit ---")
        
        # Run main developer workflow
        developer_agent = agents.terraform_developer()
        auditor_agent = agents.security_reviewer()
        finops_agent = agents.finops_specialist()

        deployer_agent = agents.deployment_specialist()

        dev_task = tasks.write_terraform_task(developer_agent, slug)
        audit_task = tasks.audit_task(auditor_agent, slug)
        cost_task = tasks.financial_analysis_task(finops_agent, slug, budget)
        deploy_task = tasks.deployment_task(deployer_agent, slug) if do_apply else None

        active_tasks = [dev_task, audit_task, cost_task]

        if deploy_task:
            active_tasks.append(deploy_task)

        crew_dev = Crew(
            agents=[developer_agent, auditor_agent, finops_agent, deployer_agent] if do_apply else [developer_agent, auditor_agent, finops_agent],
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True
        )
        
        crew_result = str(crew_dev.kickoff())
        
        # Analysis of security results for self-healing
        audit_results = auditor.run_comprehensive_scan(output_base)
        findings = audit_results.get("findings", [])
        critical_count = len([f for f in findings if f.get("severity") in ["CRITICAL", "HIGH"]])

        
        # Update best state
        if best_finding_count is None or critical_count < best_finding_count:
            best_finding_count = critical_count
            backup_result = TerraformTools._backup_workspace(slug)
            if "Backup created at " in backup_result:
                best_backup = backup_result.split("Backup created at ")[1].strip()
                print(f"  📸 Snapshot saved (best so far: {best_finding_count} issues)")
        
        # Check for Deployment Success
        is_deployed = "🚀 Deployment Successful!" in crew_result if do_apply else True

        if critical_count == 0 and is_deployed:
            print("\n✅ Phase 6 Verification SUCCESS! No security issues and deployment is live.")
            break
        
        if current_round < max_rounds:
            if args.auto_fix:
                print(f"\n🤖 Auto-Fix Enabled: Proceeding to Round {current_round + 1}...")
                choice = 'y'
            else:
                choice = input(f"\nWould you like to proceed with autonomous Fix Round {current_round + 1}? [y/n]: ").lower()
            
            if choice != 'y':
                break
            current_round += 1
        else:
            print("\n❌ Max rounds reached.")
            break

    # 4. Final Cleanup & Revert Logic
    if best_finding_count and best_finding_count > 0 and best_backup:
        print(f"\n[WARNING] Project has {best_finding_count} unresolved high-severity issues.")
        if args.auto_fix:
            print("🤖 Auto-Fix Enabled: Automatically reverting to best-known state.")
            revert_choice = 'y'
        else:
            revert_choice = input("Would you like to REVERT to the best-known state? (Recommended) [y/n]: ").lower()
            
        if revert_choice == 'y':
            TerraformTools._restore_workspace(slug, best_backup)
            print(f"Workspace reverted to best-known version with {best_finding_count} issues.")

    # 5. Final FinOps Audit & Report
    print("\nFinalizing Project Reports...")
    cost_results = estimator._execute_infracost(output_base)
    
    total_cost = float(cost_results.get("total_monthly_cost", 0))
    budget_status = "✅ WITHIN BUDGET" if total_cost <= budget else "❌ OVER BUDGET"

    final_status = "deployed" if (do_apply and is_deployed) else "generated"
    final_security = best_finding_count if best_finding_count is not None else 0
    ProjectTracker.save(slug, prompt=requirement, status=final_status,
                        budget=budget, estimated_cost=total_cost,
                        security_issues=final_security, provider=detected_provider,
                        flags=cli_flags, mermaid_diagram=mermaid_diagram)


    print("\n" + "="*50)
    print("                FINAL AGENT REPORTS")
    print("="*50)
    print(f"BUDGET STATUS: {budget_status} (Limit: ${budget})")
    print(estimator.format_report(cost_results))
    print("="*50)

    print(f"\nWorkflow complete! Final output at: output/{slug}/")
    print(f"📊 Dashboard: python dashboard.py  →  http://localhost:5000")

if __name__ == "__main__":
    main()

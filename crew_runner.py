import sys
import os
import re
from crewai import Crew, Process, Task
from agents import TerraformAgents
from tasks import TerraformTasks
from tools.security_tools import SecurityAuditor
from tools.financial_tools import CostEstimator
from tools.cloud_tools import CloudSync
from tools.terraform_tools import TerraformTools

def get_project_slug(architect_output):
    """Parses PROJECT_SLUG from architect output."""
    match = re.search(r"PROJECT_SLUG:\s*([\w-]+)", architect_output)
    if match:
        return match.group(1).strip()
    return "workspace"

def main():
    # Parse Requirement and Dynamic Budget
    budget = 100.0  # Default
    requirement = ""

    # Improved arg parsing
    args = sys.argv[1:]
    if "--budget" in args:
        idx = args.index("--budget")
        if idx + 1 < len(args):
            try:
                budget = float(args[idx+1])
                # Remove budget and its value to find the requirement
                args.pop(idx+1)
                args.pop(idx)
            except ValueError:
                print(f"Warning: Invalid budget value. Using default $100.")
    
    if args:
        requirement = " ".join(args)
    else:
        print("Error: No requirement provided.")
        sys.exit(1)

    agents = TerraformAgents()
    tasks = TerraformTasks()
    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()

    print("\n" + "="*50)
    print("      Universal AI Agent - Phase 4 (Multi-Agent)")
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

    # 2. Bootstrap Generation (Phase 3 Integration)
    is_enterprise = any(w in requirement.lower() for w in ["production", "enterprise", "scale"])
    if is_enterprise and readiness['ready']:
        print(f"Enterprise Mode: Creating bootstrap infrastructure for {readiness['provider']}...")
        bootstrap_code = cloud.generate_bootstrap_code(slug, provider=readiness['provider'])
        bootstrap_dir = os.path.join(output_base, "bootstrap")
        os.makedirs(bootstrap_dir, exist_ok=True)
        with open(os.path.join(bootstrap_dir, "main.tf"), "w", encoding="utf-8") as f:
            f.write(bootstrap_code)
        print("  + Created bootstrap/main.tf")

    # 3. Main Development & Audit Loop
    max_rounds = 3
    current_round = 1
    best_finding_count = 999
    best_backup = None

    dev_agent = agents.terraform_developer()
    reviewer_agent = agents.security_reviewer()
    finops_agent = agents.finops_specialist()

    input_context = f"Architecture Design:\n{arch_result}"

    while current_round <= max_rounds:
        print(f"\n--- [Round {current_round}/{max_rounds}] Starting Agentic Workflow ---")
        
        # 3a. Coding Task
        coding_task = tasks.write_terraform_task(dev_agent, slug)
        # 3b. Audit Task
        audit_task = tasks.audit_task(reviewer_agent, slug)
        # 3c. Financial Analysis Task (Dynamic Budget)
        finops_task = tasks.financial_analysis_task(finops_agent, slug, budget=budget)

        crew = Crew(
            agents=[dev_agent, reviewer_agent, finops_agent],
            tasks=[coding_task, audit_task, finops_task],
            process=Process.sequential,
            verbose=True
        )
        
        crew_result = str(crew.kickoff())
        
        # Comprehensive Security Audit (Ground Truth)
        print("\nVerifying with Deep Security Scan (Checkov)...")
        results = auditor.run_comprehensive_scan(output_base)
        findings = results.get("findings", [])
        critical_count = len([f for f in findings if f["severity"] in ["CRITICAL", "HIGH"]])
        
        # Track best version
        if critical_count < best_finding_count:
            best_finding_count = critical_count
            print(f"  [Progress] New best version found ({critical_count} issues). Creating snapshot...")
            best_backup = TerraformTools._backup_workspace(slug)

        if critical_count == 0:
            print("\n✅ Verification SUCCESS! No critical security issues found.")
            break
        
        # SELF-HEALING INTERACTION
        print(f"\n⚠️ Security Audit: Found {critical_count} critical/high issues.")
        print(auditor.format_report(results))
        
        if current_round < max_rounds:
            print("\n[USER INPUT REQUIRED]")
            choice = input(f"Would you like to proceed with autonomous Fix Round {current_round + 1}? [y/n]: ").lower()
            if choice != 'y':
                print("Self-healing round canceled by user.")
                break
            
            # Prepare Fix Instructions for next round
            fix_report = auditor.format_report(results)
            input_context = f"Security Audit Findings:\n{fix_report}\n\nNote: You MUST fix these high-severity issues in the next iteration."
            current_round += 1
        else:
            print("\n❌ Max rounds reached. Security standards not fully met.")
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

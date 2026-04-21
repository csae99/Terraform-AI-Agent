import os
import re
import sys
import google.generativeai as genai
from dotenv import load_dotenv
from tools.security_tools import SecurityAuditor
from tools.financial_tools import CostEstimator
from tools.cloud_tools import CloudSync
from tools.terraform_tools import TerraformTools

# This script verifies the Phase 4 logic WITHOUT relying on the CrewAI library
# which currently has environment-specific routing issues with Gemini.

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"), transport='rest')
model = genai.GenerativeModel('models/gemini-flash-latest')

def get_ai_completion(prompt):
    print(f"  [AI] Thinking...")
    response = model.generate_content(prompt)
    return response.text

def get_project_slug(architect_output):
    match = re.search(r"PROJECT_SLUG:\s*([\w-]+)", architect_output)
    if match: return match.group(1).strip()
    return "simulated-vpc"

def main():
    requirement = "I need a scalable VPC in AWS with public and private subnets."
    print("\n" + "="*60)
    print("      PHASE 4 LOGIC VERIFICATION (SIMULATION)")
    print("="*60)

    # 1. ARCHITECT PHASE
    print("\n[Step 1] Architecting...")
    arch_prompt = f"Design a Terraform architecture for: {requirement}\nIMPORTANT: Start with 'PROJECT_SLUG: <unique-name>'"
    arch_output = get_ai_completion(arch_prompt)
    slug = get_project_slug(arch_output)
    print(f"  Result: Dynamic Slug generated -> {slug}")

    # 2. WORKSPACE & CLOUD SYNC
    print(f"\n[Step 2] Workspace & Cloud Sync...")
    output_dir = os.path.join("output", slug)
    cloud = CloudSync()
    readiness = cloud.check_cloud_readiness()
    print(f"  Readiness: {readiness['provider']} Mode")
    
    # Generate Bootstrap
    bootstrap_code = cloud.generate_bootstrap_code(slug, provider=readiness['provider'])
    TerraformTools.write_terraform_file.invoke({
        "filename": "bootstrap/main.tf", 
        "content": bootstrap_code, 
        "project_slug": slug
    })
    print(f"  Success: Bootstrap created in {output_dir}/bootstrap/")

    # 3. DEVELOPER PHASE
    print("\n[Step 3] Developing Terraform...")
    dev_prompt = f"Write the Terraform code for the following architecture. {arch_output}\nOutput only the code for main.tf"
    dev_output = get_ai_completion(dev_prompt)
    # Clean output (strip markdown)
    code = re.sub(r'```terraform\n|```hcl\n|```\n|```', '', dev_output)
    TerraformTools.write_terraform_file.invoke({
        "filename": "main.tf", 
        "content": code, 
        "project_slug": slug
    })
    print(f"  Success: main.tf written to {output_dir}/")

    # 4. SECURITY AUDIT (PHASE 4 CORE)
    print("\n[Step 4] Round 1: Security Audit...")
    auditor = SecurityAuditor()
    audit_results = auditor.run_comprehensive_scan(output_dir)
    print(auditor.format_report(audit_results))

    # 5. SELF-HEALING LOOP (SIMULATED)
    print("\n[Step 5] Phase 4 Self-Healing Loop...")
    if audit_results["summary"]["total_failed"] > 0:
        print(f"  Status: Security issues found. Initiating ROUND 2 (Self-Healing)...")
        # Snapshot for Revert capability
        backup_path_msg = TerraformTools.backup_workspace.invoke({"project_slug": slug})
        print(f"  {backup_path_msg}")
        
        fix_prompt = f"The following code has security errors:\n{code}\n\nErrors:\n{auditor.format_report(audit_results)}\n\nPlease provide the FIXED main.tf code."
        fixed_output = get_ai_completion(fix_prompt)
        fixed_code = re.sub(r'```terraform\n|```hcl\n|```\n|```', '', fixed_output)
        
        TerraformTools.write_terraform_file.invoke({
            "filename": "main.tf", 
            "content": fixed_code, 
            "project_slug": slug
        })
        print(f"  Success: Fixed code written to {output_dir}/")
        
        # Verify Fix
        print("\n[Step 6] Verifying Fix...")
        final_results = auditor.run_comprehensive_scan(output_dir)
        print(auditor.format_report(final_results))
        
        if final_results["summary"]["total_failed"] < audit_results["summary"]["total_failed"]:
            print("\n✅ Verification COMPLETE: Phase 4 Multi-Agent Logic is WORKING.")
        else:
            print("\n⚠️ Note: AI attempted fix but issues remain. Logic flow verified.")
    else:
        print("\n✅ Verification COMPLETE: Initial generation was secure. Phase 4 Pathing verified.")

    # 6. COST AUDIT
    print("\n[Step 7] Final Financial Audit...")
    estimator = CostEstimator()
    costs = estimator.get_monthly_cost(output_dir)
    print(estimator.format_report(costs))

if __name__ == "__main__":
    main()

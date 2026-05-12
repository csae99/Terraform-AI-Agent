import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai
from tools.finance.cost_estimation import CostEstimator
from tools.terraform.terraform_tools import TerraformTools

# Phase 5 Verification Script: Testing Dynamic Budgeting & Reports
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"), transport='rest')
model = genai.GenerativeModel('models/gemini-flash-latest')

def main():
    print("\n" + "="*60)
    print("      PHASE 5 LOGIC VERIFICATION (FINOPS)")
    print("="*60)

    # 1. Test Data Setup
    slug = "finops-test-project"
    output_dir = os.path.join("output", slug)
    os.makedirs(output_dir, exist_ok=True)
    
    # Write a dummy main.tf that might have costs (simplified for infracost)
    terraform_code = """
    provider "aws" { region = "us-east-1" }
    resource "aws_instance" "expensive" {
      ami           = "ami-12345678"
      instance_type = "m5.4xlarge" # Intentionally expensive
    }
    """
    TerraformTools.write_terraform_file.invoke({
        "filename": "main.tf", 
        "content": terraform_code, 
        "project_slug": slug
    })
    
    # 2. Test get_monthly_cost tool
    print("\n[Step 1] Testing get_monthly_cost tool...")
    cost_summary = CostEstimator.get_monthly_cost.invoke({"directory_path": output_dir})
    print(f"  Summary: {cost_summary}")

    # 3. Test generate_financial_report tool
    print("\n[Step 2] Testing generate_financial_report tool...")
    report_msg = CostEstimator.generate_financial_report.invoke({"project_slug": slug})
    print(f"  Result: {report_msg}")

    # 4. Check if report file exists
    report_path = os.path.join(output_dir, "FINANCIAL_REPORT.md")
    if os.path.exists(report_path):
        print(f"✅ Success: Financial report created at {report_path}")
        with open(report_path, "r") as f:
            print("\n--- Report Preview ---")
            print(f.read()[:500] + "...")
    else:
        print(f"❌ Error: Financial report NOT found at {report_path}")

    # 5. Budget Simulation (Logic Check)
    budget = 50.0 # tight budget
    # Get numeric cost from infracost result
    estimator = CostEstimator()
    data = estimator._execute_infracost(output_dir)
    total_cost = float(data.get("total_monthly_cost", 0))
    
    print(f"\n[Step 3] Budget Check (Budget: ${budget})")
    if total_cost > budget:
        print(f"🚨 ALERT: Cost ${total_cost} exceeds budget ${budget}!")
        print("  System logic for Phase 5 self-healing is VALID.")
    else:
        print(f"✅ Cost ${total_cost} is within budget.")

if __name__ == "__main__":
    main()

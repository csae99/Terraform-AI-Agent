import os
import litellm
import google.generativeai as genai
from dotenv import load_dotenv
import time
from tools.security_tools import SecurityAuditor
from tools.financial_tools import CostEstimator
from tools.cloud_tools import CloudSync

def get_ai_completion(model, prompt):
    """
    Unified completion function supporting LiteLLM (OpenAI, Claude, Ollama)
    with a hard fallback to the official Google SDK for Gemini.
    """
    print(f"Calling AI model: {model}...")
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        print(f"Primary completion failed: {error_msg}")
        
        if "gemini" in model.lower():
            print("Falling back to official Google Generative AI SDK...")
            try:
                clean_model = model.split("/")[-1] if "/" in model else model
                if "flash" in clean_model:
                    clean_model = "gemini-flash-latest"
                
                genai.configure(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
                sdk_model = genai.GenerativeModel(clean_model)
                response = sdk_model.generate_content(prompt)
                return response.text
            except Exception as sdk_error:
                print(f"Official SDK fallback also failed: {str(sdk_error)}")
        
        return None

def write_files(content, output_base):
    """
    Parses FILENAME: blocks and writes them to disk.
    """
    files_created = []
    parts = content.split("FILENAME:")
    for part in parts[1:]:
        lines = part.strip().split("\n")
        rel_path = lines[0].strip()
        
        # Find any code block
        for block_marker in ["```hcl", "```terraform", "```yaml", "```markdown", "```"]:
            code_start_index = part.find(block_marker)
            if code_start_index != -1:
                code_content_start = part.find("\n", code_start_index) + 1
                code_end_index = part.rfind("```")
                if code_end_index > code_content_start:
                    code = part[code_content_start:code_end_index].strip()
                    
                    filepath = os.path.join(output_base, rel_path)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(code)
                    files_created.append(rel_path)
                    print(f"  + Created {rel_path}")
                    break
    return files_created

def main():
    load_dotenv()
    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()
    
    print("\n-------------------------------------------")
    print("Universal AI Agent - Advanced DevOps Engine")
    print("-------------------------------------------\n")

    # PRE-FLIGHT READINESS CHECK
    readiness = cloud.check_cloud_readiness()
    print(f"Cloud Sync Status: [{'READY - ' + readiness['provider'] if readiness['ready'] else 'LOCAL MODE'}]")
    if not readiness['ready']:
        print("  ! Note: No cloud credentials detected. Generation will be local-only.")
    print("")

    user_requirement = input("What infrastructure would you like to create today? ")
    if not user_requirement.strip():
        print("Requirement cannot be empty. Exiting.")
        return

    model = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    
    # 1. INITIAL GENERATION
    prompt = f"""
    You are a Senior Terraform Developer & Cloud Architect. 
    Task: Create a MODULAR and REUSABLE Terraform setup based on: "{user_requirement}"
    
    Requirements:
    1. Define a PROJECT_SLUG.
    2. Modular structure: Root calls modules in modules/ directory.
    3. Generate a README.md with deployment instructions.
    4. Security: Follow AWS Best practices.
    5. Cost Awareness: Prefer cost-effective resources unless high performance is requested.
    6. ENTERPRISE MODE: If the user mentions "Production", "Enterprise", or "Scale", you MUST:
       - Include a `backend.tf` in the root using S3 (AWS) or equivalent.
       - Enforce `-tf-state` suffix for bucket names.
       - Use `encrypt = true`.

    OUTPUT FORMAT:
    PROJECT_SLUG: [slug]
    
    FILENAME: [path]
    ```[language]
    [code]
    ```
    """

    content = get_ai_completion(model, prompt)
    if not content:
        print("\nAll completion attempts failed.")
        return

    # Parse Slug
    slug = "workspace"
    if "PROJECT_SLUG:" in content:
        slug = content.split("PROJECT_SLUG:")[1].split("\n")[0].strip()
    
    output_base = os.path.join("output", slug)
    print(f"\nBuilding Workspace: {output_base}/")
    write_files(content, output_base)

    # ENTERPRISE BOOTSTRAP GENERATION
    is_enterprise = any(word in user_requirement.lower() for word in ["production", "enterprise", "scale", "remote state"])
    if is_enterprise and readiness['ready']:
        print(f"\nEnterprise Mode Detected. Generating Bootstrap Infrastructure for {readiness['provider']}...")
        bootstrap_code = cloud.generate_bootstrap_code(slug, provider=readiness['provider'])
        bootstrap_dir = os.path.join(output_base, "bootstrap")
        os.makedirs(bootstrap_dir, exist_ok=True)
        with open(os.path.join(bootstrap_dir, "main.tf"), "w", encoding="utf-8") as f:
            f.write(bootstrap_code)
        print(f"  + Created bootstrap/main.tf (State Bucket + Lock Table)")

    # 2. SECURITY AUDIT & SELF-HEALING
    print("\nStarting Automated Security Audit (Checkov)...")
    audit_results = auditor.run_comprehensive_scan(output_base, mode="checkov")
    findings = audit_results.get("findings", [])
    critical_issues = [f for f in findings if f["severity"] in ["CRITICAL", "HIGH"]]
    
    if critical_issues:
        print(f"  [Healing] Found {len(critical_issues)} high-severity issues. Fix round started...")
        fix_report = auditor.format_report({"summary": {"total_failed": len(critical_issues), "passed": False, "engine": "checkov"}, "findings": critical_issues})
        fix_prompt = f"Fix the security issues in this Terraform project:\n\n{fix_report}\n\nContext:\n{content}"
        fixed_content = get_ai_completion(model, fix_prompt)
        if fixed_content:
            write_files(fixed_content, output_base)
            audit_results = auditor.run_comprehensive_scan(output_base, mode="checkov")

    # 3. FINANCIAL INTELLIGENCE (COST ESTIMATION)
    print("\nStarting Financial Audit (Infracost)...")
    cost_results = estimator.get_monthly_cost(output_base)

    # 4. FINAL REPORTS
    print("\n" + "="*50)
    print("                FINAL AGENT REPORTS")
    print("="*50)
    print(auditor.format_report(audit_results))
    print("\n" + estimator.format_report(cost_results))
    print("="*50)
    
    # Append cost to project README
    readme_path = os.path.join(output_base, "README.md")
    if os.path.exists(readme_path):
        cost_info = "\n\n## 💰 Estimated Infrastructure Cost\n"
        cost_info += estimator.format_report(cost_results)
        with open(readme_path, "a", encoding="utf-8") as f:
            f.write(cost_info)

    print(f"\nGeneration complete! Folder: 'output/{slug}/'")
    if "AUTHENTICATION_REQUIRED" in str(cost_results):
        print("\n[TIP] To enable real cost estimates, run 'infracost auth login' in your terminal.")

if __name__ == "__main__":
    main()

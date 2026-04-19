import os
import litellm
import google.generativeai as genai
from dotenv import load_dotenv
import time
from tools.security_tools import SecurityAuditor

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
    
    print("\n-------------------------------------------")
    print("Universal AI Agent - Security-Aware Engine")
    print("-------------------------------------------\n")

    user_requirement = input("What infrastructure would you like to create today? ")
    if not user_requirement.strip():
        print("Requirement cannot be empty. Exiting.")
        return

    model = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    
    # 1. INITIAL GENERATION
    prompt = f"""
    You are a Senior Terraform Developer. 
    Task: Create a MODULAR and REUSABLE Terraform setup based on: "{user_requirement}"
    
    Requirements:
    1. Define a PROJECT_SLUG (e.g., 'aws-s3-website-v1').
    2. Modular structure: Root calls modules in modules/ directory.
    3. Generate a README.md with deployment instructions.
    4. Security: Follow AWS Best practices. Do not leave resources open to the public unless explicitly asked.

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

    # 2. SECURITY AUDIT & SELF-HEALING (Using Comprehensive Mode)
    # Default is Checkov-Docker
    audit_results = auditor.run_comprehensive_scan(output_base, mode="checkov")
    
    # Filter for Critical/High issues (Checkov uses HIGH/CRITICAL)
    findings = audit_results.get("findings", [])
    critical_issues = [f for f in findings if f["severity"] in ["CRITICAL", "HIGH"]]
    
    if critical_issues:
        print(f"  [Healing] Found {len(critical_issues)} high-severity issues. Fix round started...")
        
        # Prepare fix prompt
        fix_report = auditor.format_report({"summary": {"total_failed": len(critical_issues), "passed": False, "engine": "checkov"}, "findings": critical_issues})
        
        fix_prompt = f"""
        You are a Senior Security Engineer. 
        The following Terraform code was generated for requirement: "{user_requirement}"
        
        However, a deep security audit (Checkov) found the following issues:
        
        {fix_report}
        
        Task: Please update the complete project code to resolve these security issues. 
        Include all modules and root files. Follow the same FILENAME: format.
        
        Context:
        {content}
        """
        
        fixed_content = get_ai_completion(model, fix_prompt)
        if fixed_content:
            print("  [Healing] Applying security patches...")
            write_files(fixed_content, output_base)
            
            # Final Sanity Check
            print("  [Audit] Final verification scan...")
            audit_results = auditor.run_comprehensive_scan(output_base, mode="checkov")
        else:
            print("  [Healing] Failed to get security fixes from AI.")

    # 3. FINAL REPORTing
    print("\n--- FINAL SECURITY REPORT ---")
    print(auditor.format_report(audit_results))
    
    print(f"\nGeneration complete! folder 'output/{slug}/'")
    print(f"Deployment instructions in 'output/{slug}/README.md'.")

if __name__ == "__main__":
    main()

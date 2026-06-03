"""
Reflection Engine - Dynamic self-debugging layer.

Instructs LLM to reflect on Terraform error logs and code files,
generating dynamic correction advice on-the-fly when no matching
static signature exists in the failure patterns memory.
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("terraform-reflection")


def reflect_on_error(error_text: str, project_slug: str) -> Optional[Dict[str, str]]:
    """Analyzes the error log, reads relevant code files, and queries the LLM
    for dynamic correction advice.

    Args:
        error_text: Raw error log from Terraform CLI or auditor.
        project_slug: Slug identifying the project folder in output/

    Returns:
        Dict with keys 'cause', 'fix_advice', and 'corrected_snippet' if successful, or None.
    """
    import litellm

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("[Reflection] Skipped: No API key configured.")
        return None

    model = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    project_dir = os.path.join("output", project_slug)
    if not os.path.isdir(project_dir):
        logger.warning(f"[Reflection] Skipped: Project workspace {project_dir} not found.")
        return None

    # 1. Identify relevant files from the error log
    tf_files = _find_referenced_files(error_text, project_dir)
    if not tf_files:
        # Fallback to reading root files
        for f in ["main.tf", "variables.tf", "outputs.tf"]:
            p = os.path.join(project_dir, f)
            if os.path.exists(p):
                tf_files.append(p)

    # 2. Read file contents
    code_context = []
    for filepath in tf_files[:5]:  # Limit to top 5 files to avoid context limits
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            rel_path = os.path.relpath(filepath, project_dir)
            code_context.append(f"--- File: {rel_path} ---\n{content}\n")
        except Exception as e:
            logger.warning(f"[Reflection] Could not read file {filepath}: {e}")

    if not code_context:
        logger.warning("[Reflection] Skipped: No code context files available.")
        return None

    context_str = "\n".join(code_context)

    # 3. Dynamic Search for Error Documentation
    search_query = ""
    lines = [line.strip() for line in error_text.split("\n") if line.strip()]
    error_detail_lines = []
    for line in lines:
        if "Error:" in line:
            error_detail_lines.append(line)
        elif "not expected" in line or "Unsupported" in line or "Invalid" in line:
            error_detail_lines.append(line)
    
    if error_detail_lines:
        search_query = " ".join(error_detail_lines)
    elif lines:
        search_query = " ".join(lines[:2])
    
    # Strip any specific file paths or line numbers to make the query generic and clean
    search_query = re.sub(r'on\s+[\w\\/\-._]+\.tf\s+line\s+\d+', '', search_query)
    search_query = re.sub(r'[:\(\)]', ' ', search_query)
    search_query = " ".join(search_query.split()) # normalize spaces
    
    search_results = ""
    if search_query:
        logger.info(f"[Reflection] Performing documentation search for: '{search_query}'")
        try:
            from tools.terraform.terraform_tools import TerraformTools
            search_results = TerraformTools._search_terraform_documentation(search_query)
        except Exception as e:
            logger.warning(f"[Reflection] Search failed: {e}")

    search_context = ""
    if search_results:
        search_context = f"\n\nDOCUMENTATION SEARCH RESULTS (Use this to find correct argument names or API renames):\n\"\"\"\n{search_results}\n\"\"\""

    # 4. Construct prompt
    prompt = f"""
You are an expert Terraform and Cloud DevOps debugger.
We encountered a compilation, validation, or deployment failure in our Terraform run.
Please analyze the error log and the relevant code files to provide a precise explanation of the problem and the exact corrected code block to fix it.

ERROR LOG:
\"\"\"{error_text}\"\"\"{search_context}

CODE FILES IN CONTEXT:
\"\"\"{context_str}\"\"\"

Your task is to:
1. Explain the exact cause of the error (be specific about which argument, resource, or block is wrong).
2. Write a clear, developer-facing fix advice (e.g. "Move the enable_auto_scaling argument inside the default_node_pool nested block").
3. Provide the exact corrected code snippet for the failing resource/block.

Return the output strictly in the following JSON format:
{{
  "cause": "...",
  "fix_advice": "...",
  "corrected_snippet": "..."
}}
"""
    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        
        # Verify keys
        if "cause" in parsed and "fix_advice" in parsed and "corrected_snippet" in parsed:
            logger.info(f"[Reflection] Successfully generated advice for slug '{project_slug}'.")
            return {
                "cause": parsed["cause"],
                "fix_advice": parsed["fix_advice"],
                "corrected_snippet": parsed["corrected_snippet"]
            }
        else:
            logger.warning("[Reflection] Error: JSON returned was missing required keys.")
            return None
    except Exception as e:
        logger.warning(f"[Reflection] Error calling LLM reflection: {e}")
        return None


def _find_referenced_files(error_text: str, project_dir: str) -> List[str]:
    """Helper to parse relative or absolute file paths from the error text."""
    found_files = []
    
    # Matches patterns like: 'on modules\aks\main.tf line 19' or 'on main.tf line 5' or absolute path strings
    # Regex searches for anything ending in .tf
    paths = re.findall(r'([\w\\/\-._]+\.tf)', error_text)
    
    for path in paths:
        # Check absolute path
        if os.path.isabs(path) and os.path.exists(path):
            if path not in found_files:
                found_files.append(path)
        else:
            # Check relative to project dir
            # Normalize path delimiters
            normalized_path = path.replace("\\", "/")
            full_path = os.path.join(project_dir, normalized_path)
            if os.path.exists(full_path) and full_path not in found_files:
                found_files.append(full_path)
                
            # Check recursive search in project dir
            for root, _, files in os.walk(project_dir):
                for f in files:
                    if f.lower() == os.path.basename(path).lower():
                        match_path = os.path.join(root, f)
                        if match_path not in found_files:
                            found_files.append(match_path)

    return found_files

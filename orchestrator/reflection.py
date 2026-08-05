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

    model = os.getenv("DEFAULT_MODEL", "gemini/gemini-1.5-flash")
    provider = "gemini"
    if model and "/" in model:
        provider = model.split("/")[0].lower()
    elif model and model.startswith("gpt"):
        provider = "openai"
    elif model and model.startswith("claude"):
        provider = "anthropic"

    # Map provider to env vars
    key_map = {
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "google_ai": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "nvidia": ["NVIDIA_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
    }
    
    candidate_envs = key_map.get(provider, ["GEMINI_API_KEY", "GOOGLE_API_KEY"])
    api_key = None
    for env_name in candidate_envs:
        api_key = os.getenv(env_name)
        if api_key:
            break
            
    if not api_key:
        # Fallback to any present API key
        for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY", "NVIDIA_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"]:
            api_key = os.getenv(k)
            if api_key:
                break
                
    if not api_key:
        logger.warning(f"[Reflection] Skipped: No API key configured for provider '{provider}'.")
        return None
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
            raw_search_results = TerraformTools._search_terraform_documentation(search_query)
            search_results = _rank_and_filter_snippets(raw_search_results, search_query)
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
2. Write a clear, developer-facing fix advice (e.g. "Ensure the subnet CIDR block is defined as a variable instead of being hardcoded in the subnets block").
3. Provide the exact corrected code snippet for the failing resource/block.
4. Estimate your confidence in this solution as a float between 0.0 (completely unsure) and 1.0 (absolutely certain).

Return the output strictly in the following JSON format:
{{
  "cause": "...",
  "fix_advice": "...",
  "corrected_snippet": "...",
  "confidence": 0.85
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
            confidence = parsed.get("confidence", 1.0)
            try:
                confidence = float(confidence)
            except (ValueError, TypeError):
                confidence = 1.0
                
            logger.info(f"[Reflection] Generated advice for slug '{project_slug}' with confidence {confidence}.")
            if confidence < 0.6:
                logger.warning(f"[Reflection] Discarded: confidence {confidence} is below threshold (0.6).")
                return None
                
            snippet = parsed["corrected_snippet"]
            if not validate_hcl_syntax(snippet):
                logger.warning(f"[Reflection] Discarded: HCL bracket syntax validation failed on suggested snippet.")
                return None
                
            return {
                "cause": parsed["cause"],
                "fix_advice": parsed["fix_advice"],
                "corrected_snippet": snippet,
                "confidence": confidence
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


def _rank_and_filter_snippets(search_results: str, query: str) -> str:
    """Ranks documentation search snippets by keyword relevance and returns the top 2-3."""
    if not search_results or "No relevant documentation" in search_results:
        return ""
        
    # Split into individual snippets
    raw_snippets = [s.strip() for s in search_results.split("\n\n") if s.strip()]
    
    # Tokenize query, filter out common stop words
    stop_words = {"terraform", "error", "failed", "in", "the", "is", "a", "on", "line", "not", "expected", "unsupported", "argument", "invalid"}
    query_tokens = [t.lower() for t in re.findall(r'\b\w+\b', query) if t.lower() not in stop_words]
    
    if not query_tokens:
        # Fall back to using the full query words if all are stop words
        query_tokens = [t.lower() for t in re.findall(r'\b\w+\b', query)]
        
    scored_snippets = []
    for snippet in raw_snippets:
        # Strip leading "- " if present
        clean_snippet = snippet
        if clean_snippet.startswith("- "):
            clean_snippet = clean_snippet[2:]
            
        snippet_lower = clean_snippet.lower()
        score = 0
        for token in query_tokens:
            if token in snippet_lower:
                score += 1
                
        scored_snippets.append((score, clean_snippet))
        
    # Sort descending by score
    scored_snippets.sort(key=lambda x: x[0], reverse=True)
    
    # Take top 3 snippets
    top_snippets = [item[1] for item in scored_snippets[:3]]
    
    return "\n\n".join(f"- {s}" for s in top_snippets)


def validate_hcl_syntax(snippet: str) -> bool:
    """Sanity check to verify basic HCL syntax (balanced braces/brackets)."""
    stack = []
    brackets = {'{': '}', '[': ']', '(': ')'}
    for char in snippet:
        if char in brackets:
            stack.append(char)
        elif char in brackets.values():
            if not stack:
                return False
            # Find matching open bracket
            matching_open = next(k for k, v in brackets.items() if v == char)
            if stack.pop() != matching_open:
                return False
    return len(stack) == 0

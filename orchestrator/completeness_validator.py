"""
Completeness Validator – detects partial file generation.

After the developer agent finishes, this module scans the output directory
to verify that all expected modules and root files were actually created.
This catches the common failure mode where the LLM stops writing files
mid-generation due to rate limits or context window exhaustion.
"""

import os
import re
from typing import Dict, List, Optional


# Minimum set of root files every Terraform project should have
REQUIRED_ROOT_FILES = ["main.tf", "variables.tf", "outputs.tf"]

# Every module directory should contain at least main.tf
REQUIRED_MODULE_FILES = ["main.tf"]


def _extract_expected_modules_from_arch(arch_result: str) -> List[str]:
    """Extract module names referenced in the architect's design document.

    Looks for patterns like:
        - module "vpc" { source = "./modules/vpc" }
        - modules/aks/main.tf
        - `modules/nsg`
        - **Module: vnet**
    """
    modules = set()

    # Pattern 1: module "name" { source = "./modules/name" }
    for m in re.finditer(r'module\s+"([^"]+)"', arch_result):
        modules.add(m.group(1))

    # Pattern 2: source = "./modules/xxx"
    for m in re.finditer(r'source\s*=\s*"\.?/?modules/([^"]+)"', arch_result):
        modules.add(m.group(1).strip("/"))

    # Pattern 3: modules/xxx/main.tf or modules/xxx
    for m in re.finditer(r'modules/([a-z0-9_-]+)', arch_result, re.IGNORECASE):
        modules.add(m.group(1))

    # Pattern 4: **Module: xxx** or ### Module: xxx
    for m in re.finditer(r'(?:\*\*|###?\s*)Module[:\s]+([a-z0-9_-]+)', arch_result, re.IGNORECASE):
        modules.add(m.group(1).lower())

    # Filter out noise (very short or clearly not module names)
    modules = {m for m in modules if len(m) > 1 and m not in {"tf", "md", "hcl"}}

    return sorted(modules)


def _extract_expected_modules_from_root_main(output_dir: str) -> List[str]:
    """Parse the root main.tf to find module source references.

    Falls back to this if the architect output doesn't clearly list modules.
    """
    main_tf = os.path.join(output_dir, "main.tf")
    if not os.path.exists(main_tf):
        return []

    try:
        with open(main_tf, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    modules = set()
    for m in re.finditer(r'source\s*=\s*"\.?/?modules/([^"]+)"', content):
        modules.add(m.group(1).strip("/"))

    return sorted(modules)


def validate_workspace_completeness(
    slug: str,
    arch_result: str = "",
    output_base: str = "output",
) -> Dict:
    """Validate that the developer agent generated all expected files.

    Args:
        slug: The project slug (e.g. "azure-aks-public-cluster").
        arch_result: The architect's raw design output.
        output_base: Base output directory (default: "output").

    Returns:
        dict with keys:
            is_complete (bool): True if all expected files exist.
            missing_root_files (list[str]): Root files that are missing.
            missing_modules (dict[str, list[str]]): Module name -> missing files.
            empty_files (list[str]): Files that exist but are 0 bytes.
            existing_files (list[str]): Files that were successfully generated.
            expected_modules (list[str]): All modules we expected to find.
    """
    output_dir = os.path.join(output_base, slug)
    result = {
        "is_complete": True,
        "missing_root_files": [],
        "missing_modules": {},
        "empty_files": [],
        "existing_files": [],
        "expected_modules": [],
    }

    if not os.path.exists(output_dir):
        result["is_complete"] = False
        result["missing_root_files"] = REQUIRED_ROOT_FILES[:]
        return result

    # ── 1. Check root files ──────────────────────────────────────────
    for root_file in REQUIRED_ROOT_FILES:
        filepath = os.path.join(output_dir, root_file)
        if not os.path.exists(filepath):
            result["missing_root_files"].append(root_file)
            result["is_complete"] = False
        elif os.path.getsize(filepath) == 0:
            result["empty_files"].append(root_file)
            result["is_complete"] = False
        else:
            result["existing_files"].append(root_file)

    # ── 2. Determine expected modules ────────────────────────────────
    expected_modules = _extract_expected_modules_from_arch(arch_result)

    # Also check what the root main.tf references (if it exists)
    root_main_modules = _extract_expected_modules_from_root_main(output_dir)
    for mod in root_main_modules:
        if mod not in expected_modules:
            expected_modules.append(mod)

    result["expected_modules"] = expected_modules

    # ── 3. Check each expected module directory ──────────────────────
    modules_dir = os.path.join(output_dir, "modules")
    for mod_name in expected_modules:
        mod_dir = os.path.join(modules_dir, mod_name)
        if not os.path.exists(mod_dir):
            result["missing_modules"][mod_name] = REQUIRED_MODULE_FILES[:]
            result["is_complete"] = False
            continue

        missing_in_mod = []
        for req_file in REQUIRED_MODULE_FILES:
            fpath = os.path.join(mod_dir, req_file)
            if not os.path.exists(fpath):
                missing_in_mod.append(req_file)
            elif os.path.getsize(fpath) == 0:
                result["empty_files"].append(f"modules/{mod_name}/{req_file}")
            else:
                result["existing_files"].append(f"modules/{mod_name}/{req_file}")

        if missing_in_mod:
            result["missing_modules"][mod_name] = missing_in_mod
            result["is_complete"] = False

    # ── 4. Scan for any other files that were successfully written ───
    for root, dirs, files in os.walk(output_dir):
        # Skip hidden dirs and .terraform
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".tf") or f.endswith(".md"):
                rel = os.path.relpath(os.path.join(root, f), output_dir)
                rel = rel.replace("\\", "/")
                if rel not in result["existing_files"]:
                    fpath = os.path.join(root, f)
                    if os.path.getsize(fpath) == 0:
                        if rel not in result["empty_files"]:
                            result["empty_files"].append(rel)
                    else:
                        result["existing_files"].append(rel)

    return result


def format_completeness_report(report: Dict) -> str:
    """Format the completeness report for logging."""
    lines = []
    lines.append("\n📋 Workspace Completeness Check:")

    if report["is_complete"]:
        lines.append("  ✅ All expected files are present!")
        lines.append(f"  📁 Files found: {len(report['existing_files'])}")
        return "\n".join(lines)

    lines.append("  ❌ INCOMPLETE - Missing files detected:")

    if report["missing_root_files"]:
        lines.append(f"  🔴 Missing root files: {', '.join(report['missing_root_files'])}")

    if report["missing_modules"]:
        for mod, files in report["missing_modules"].items():
            lines.append(f"  🔴 Missing module '{mod}': {', '.join(files)}")

    if report["empty_files"]:
        lines.append(f"  ⚠️  Empty files (0 bytes): {', '.join(report['empty_files'])}")

    if report["existing_files"]:
        lines.append(f"  ✅ Successfully generated: {', '.join(report['existing_files'])}")

    return "\n".join(lines)

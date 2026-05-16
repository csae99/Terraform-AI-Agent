"""
CLI Entry-Point for the Multi-Agent Terraform Platform.

This is now a thin wrapper that parses arguments and delegates
all execution to the central orchestrator pipeline.
"""

import sys
import io
import os
import argparse

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure project root is on sys.path so imports work without PYTHONPATH
_project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.chdir(_project_root)

os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from orchestrator.pipeline import run_full_pipeline, run_destroy_pipeline


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

    # Handle Destructive Actions
    if args.destroy:
        run_destroy_pipeline(args.destroy, model_name=args.model, model_key=args.model_key)
        return

    if not args.prompt:
        parser.print_help()
        return

    # Build CLI flags for tracking
    cli_flags = ["--apply"] if args.apply else []
    if args.budget != 100.0:
        cli_flags.append(f"--budget={args.budget}")
    if args.auto_fix:
        cli_flags.append("--auto-fix")

    owner_id = os.getenv("owner_id")

    run_full_pipeline(
        prompt=args.prompt,
        budget=args.budget,
        do_apply=args.apply,
        auto_fix=args.auto_fix,
        model_name=args.model,
        model_key=args.model_key,
        owner_id=owner_id,
        cli_flags=cli_flags,
    )


if __name__ == "__main__":
    main()

import os
import json
import re
import glob
from datetime import datetime


class ProjectTracker:
    """
    Manages structured metadata (project.json) for each Terraform workspace.
    Provides the data foundation for the Dashboard API.
    """

    OUTPUT_DIR = "output"

    @staticmethod
    def save(slug, prompt="", status="generated", budget=0.0,
             estimated_cost=0.0, security_issues=0, provider="Local", flags=None):
        """Save or update project metadata."""
        project_dir = os.path.join(ProjectTracker.OUTPUT_DIR, slug)
        meta_path = os.path.join(project_dir, "project.json")

        # Load existing metadata if present (preserve created_at)
        existing = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing = {}

        now = datetime.now().isoformat(timespec="seconds")

        meta = {
            "slug": slug,
            "prompt": prompt or existing.get("prompt", ""),
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "status": status,
            "budget": budget,
            "estimated_cost": estimated_cost,
            "security_issues": security_issues,
            "provider": provider,
            "flags": flags or existing.get("flags", []),
        }

        os.makedirs(project_dir, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        return meta

    @staticmethod
    def load(slug):
        """Load metadata for a single project."""
        meta_path = os.path.join(ProjectTracker.OUTPUT_DIR, slug, "project.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    @staticmethod
    def load_all():
        """Load metadata for ALL projects in the output directory."""
        projects = []
        output_dir = ProjectTracker.OUTPUT_DIR
        if not os.path.exists(output_dir):
            return projects

        for entry in sorted(os.listdir(output_dir)):
            full_path = os.path.join(output_dir, entry)
            if not os.path.isdir(full_path) or entry.startswith("."):
                continue

            meta = ProjectTracker.load(entry)
            if meta:
                projects.append(meta)
            else:
                # Auto-generate metadata from existing files
                projects.append(ProjectTracker._infer_metadata(entry))

        return projects

    @staticmethod
    def _infer_metadata(slug):
        """Infer project metadata from filesystem when project.json is missing."""
        project_dir = os.path.join(ProjectTracker.OUTPUT_DIR, slug)

        # Detect provider from main.tf
        provider = "Local"
        main_tf = os.path.join(project_dir, "main.tf")
        if os.path.exists(main_tf):
            try:
                with open(main_tf, "r", encoding="utf-8") as f:
                    content = f.read()
                if 'provider "aws"' in content or "hashicorp/aws" in content:
                    provider = "AWS"
                elif 'provider "azurerm"' in content:
                    provider = "Azure"
                elif 'provider "google"' in content:
                    provider = "GCP"
            except IOError:
                pass

        # Detect status from tfstate
        has_state = os.path.exists(os.path.join(project_dir, "terraform.tfstate"))
        status = "deployed" if has_state else "generated"

        # Parse cost from FINANCIAL_REPORT.md
        estimated_cost = 0.0
        budget = 100.0
        report_path = os.path.join(project_dir, "FINANCIAL_REPORT.md")
        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    report_content = f.read()
                cost_match = re.search(r"Projected Cost.*?\$([0-9.]+)", report_content)
                if cost_match:
                    estimated_cost = float(cost_match.group(1))
                budget_match = re.search(r"Allocated Budget.*?\$([0-9.]+)", report_content)
                if budget_match:
                    budget = float(budget_match.group(1))
            except IOError:
                pass

        # Get creation time from directory
        try:
            created_ts = os.path.getctime(project_dir)
            created_at = datetime.fromtimestamp(created_ts).isoformat(timespec="seconds")
        except OSError:
            created_at = datetime.now().isoformat(timespec="seconds")

        meta = {
            "slug": slug,
            "prompt": f"(Inferred from {slug})",
            "created_at": created_at,
            "updated_at": created_at,
            "status": status,
            "budget": budget,
            "estimated_cost": estimated_cost,
            "security_issues": 0,
            "provider": provider,
            "flags": [],
        }

        # Save it so we don't infer again
        meta_path = os.path.join(project_dir, "project.json")
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except IOError:
            pass

        return meta

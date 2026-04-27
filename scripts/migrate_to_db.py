import os
import json
import sys

# Add parent directory to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.project_tracker import ProjectTracker

def migrate():
    print("🚀 Starting migration of JSON metadata to SQL Database...")
    output_dir = "output"
    
    if not os.path.exists(output_dir):
        print("No output directory found. Nothing to migrate.")
        return

    count = 0
    for slug in os.listdir(output_dir):
        project_dir = os.path.join(output_dir, slug)
        if not os.path.isdir(project_dir):
            continue
            
        json_path = os.path.join(project_dir, "project.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                print(f"  📦 Migrating project: {slug}")
                ProjectTracker.save(
                    slug=slug,
                    prompt=data.get("prompt", ""),
                    status=data.get("status", "generated"),
                    budget=data.get("budget", 100.0),
                    estimated_cost=data.get("estimated_cost", 0.0),
                    security_issues=data.get("security_issues", 0),
                    provider=data.get("provider", "Local"),
                    flags=data.get("flags", []),
                    mermaid_diagram=data.get("mermaid_diagram", ""),
                    drift_status=data.get("drift_status", "unknown")
                )
                count += 1
            except Exception as e:
                print(f"  ❌ Error migrating {slug}: {str(e)}")

    print(f"\n✅ Migration finished! {count} projects moved to SQL.")

if __name__ == "__main__":
    migrate()

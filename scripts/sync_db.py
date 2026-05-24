import os
import sys
import re

# Add parent directory to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tools.project.tracker import ProjectTracker

def sync():
    print("🚀 Starting sync of FINANCIAL_REPORT.md costs to SQL Database...")
    output_dir = "output"
    
    if not os.path.exists(output_dir):
        print("No output directory found. Nothing to sync.")
        return

    count = 0
    for slug in os.listdir(output_dir):
        project_dir = os.path.join(output_dir, slug)
        if not os.path.isdir(project_dir):
            continue
            
        report_path = os.path.join(project_dir, "FINANCIAL_REPORT.md")
        if os.path.exists(report_path):
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Regex match for projected cost (e.g. **Projected Cost:** `$1198.28`)
                match = re.search(r"Projected\s*Cost[^\d\.]+?([\d\.]+)", content, re.IGNORECASE)
                if match:
                    cost = float(match.group(1))
                    print(f"  📦 Synced project: {slug} with cost: ${cost}")
                    ProjectTracker.save(slug=slug, estimated_cost=cost)
                    count += 1
                else:
                    print(f"  ⚠️ Could not find projected cost in report for {slug}")
            except Exception as e:
                print(f"  ❌ Error syncing {slug}: {str(e)}")

    print(f"\n✅ Sync finished! {count} projects updated in DB.")

if __name__ == "__main__":
    sync()

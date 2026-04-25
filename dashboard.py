"""
Terraform AI Agent - Web Dashboard (Phase 6b: Interactive)
Usage:
    python dashboard.py
    -> http://localhost:5000
"""
import os
import glob
import json
import sys
import io
import subprocess
import threading
from flask import Flask, jsonify, send_from_directory, abort, request

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from tools.project_tracker import ProjectTracker

app = Flask(__name__, static_folder="static", static_url_path="/static")

OUTPUT_DIR = "output"

# In-memory store for active process logs
active_logs = {}

def run_agent_workflow(prompt, budget, apply, credentials=None, ai_config=None):
    """Background task to run the crew_runner.py process."""
    cmd = [sys.executable, "crew_runner.py", prompt, "--budget", str(budget), "--auto-fix"]
    if apply:
        cmd.append("--apply")
    
    # Handle AI Config overrides
    if ai_config:
        if ai_config.get("model"):
            # Ensure model has provider prefix if needed
            model = ai_config.get("model")
            provider = ai_config.get("provider")
            if "/" not in model and provider:
                model = f"{provider}/{model}"
            cmd.extend(["--model", model])
        if ai_config.get("key"):
            cmd.extend(["--model-key", ai_config.get("key")])

    # We use a unique ID for this run's logs (simple prompt-based slug for now)
    temp_slug = "active-run"
    active_logs[temp_slug] = "🚀 Starting Multi-Agent Workflow...\n"
    
    # Inject user-provided credentials into the environment
    env = os.environ.copy()
    if credentials:
        for key, value in credentials.items():
            if value: # Only set if a value was provided
                env[key] = value

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            env=env
        )
        
        for line in iter(process.stdout.readline, ''):
            active_logs[temp_slug] += line
            # Keep log size reasonable (last 500 lines)
            lines = active_logs[temp_slug].split('\n')
            if len(lines) > 500:
                active_logs[temp_slug] = '\n'.join(lines[-500:])
            
        process.stdout.close()
        process.wait()
        active_logs[temp_slug] += f"\n✅ Workflow Finished with exit code {process.returncode}\n"
    except Exception as e:
        active_logs[temp_slug] += f"\n❌ Error: {str(e)}\n"

# ─── Page Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the dashboard SPA."""
    return send_from_directory("static", "index.html")


# ─── API Routes ────────────────────────────────────────────────────

@app.route("/api/projects")
def list_projects():
    """Return metadata for all projects."""
    projects = ProjectTracker.load_all()
    return jsonify(projects)

@app.route("/api/generate", methods=["POST"])
def generate_infrastructure():
    """Trigger the multi-agent workflow."""
    data = request.json
    prompt = data.get("prompt")
    budget = data.get("budget", 100)
    apply = data.get("apply", False)
    credentials = data.get("credentials")
    ai_config = data.get("ai_config")

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    # Start workflow in a background thread
    thread = threading.Thread(target=run_agent_workflow, args=(prompt, budget, apply, credentials, ai_config))
    thread.daemon = True
    thread.start()

    return jsonify({"message": "Workflow started", "status": "processing"})


@app.route("/api/logs/active")
def get_active_logs():
    """Stream active logs to the dashboard."""
    return jsonify({"logs": active_logs.get("active-run", "No active run.")})


@app.route("/api/projects/<slug>")
def get_project(slug):
    """Return detailed metadata for a single project."""
    meta = ProjectTracker.load(slug)
    if not meta:
        # Try to infer from filesystem
        project_dir = os.path.join(OUTPUT_DIR, slug)
        if os.path.isdir(project_dir):
            meta = ProjectTracker._infer_metadata(slug)
        else:
            abort(404, description=f"Project '{slug}' not found")
    return jsonify(meta)


@app.route("/api/projects/<slug>/code")
def get_project_code(slug):
    """Return all .tf file contents for a project."""
    project_dir = os.path.join(OUTPUT_DIR, slug)
    if not os.path.isdir(project_dir):
        abort(404)

    tf_files = {}
    # Collect root-level .tf files
    for tf in sorted(glob.glob(os.path.join(project_dir, "*.tf"))):
        filename = os.path.basename(tf)
        try:
            with open(tf, "r", encoding="utf-8") as f:
                tf_files[filename] = f.read()
        except IOError:
            tf_files[filename] = "(Error reading file)"

    # Collect module .tf files
    modules_dir = os.path.join(project_dir, "modules")
    if os.path.isdir(modules_dir):
        for tf in sorted(glob.glob(os.path.join(modules_dir, "**", "*.tf"), recursive=True)):
            rel = os.path.relpath(tf, project_dir).replace("\\", "/")
            try:
                with open(tf, "r", encoding="utf-8") as f:
                    tf_files[rel] = f.read()
            except IOError:
                tf_files[rel] = "(Error reading file)"

    return jsonify(tf_files)


@app.route("/api/projects/<slug>/report")
def get_project_report(slug):
    """Return the FINANCIAL_REPORT.md content."""
    report_path = os.path.join(OUTPUT_DIR, slug, "FINANCIAL_REPORT.md")
    if not os.path.exists(report_path):
        return jsonify({"content": "No financial report available.", "exists": False})

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content, "exists": True})
    except IOError:
        return jsonify({"content": "Error reading report.", "exists": False})


@app.route("/api/projects/<slug>/logs/<log_type>")
def get_project_logs(slug, log_type):
    """Return deployment logs (plan, apply, destroy)."""
    valid_types = ["terraform_plan", "terraform_apply", "terraform_destroy",
                   "terraform_plan_destroy"]
    if log_type not in valid_types:
        abort(400, description=f"Invalid log type. Valid: {valid_types}")

    log_path = os.path.join(OUTPUT_DIR, slug, "logs", f"{log_type}.log")
    if not os.path.exists(log_path):
        return jsonify({"content": f"No {log_type} log available.", "exists": False})

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content, "exists": True})
    except IOError:
        return jsonify({"content": "Error reading log.", "exists": False})


@app.route("/api/projects/<slug>/readme")
def get_project_readme(slug):
    """Return the project README.md content."""
    readme_path = os.path.join(OUTPUT_DIR, slug, "README.md")
    if not os.path.exists(readme_path):
        return jsonify({"content": "No README available.", "exists": False})

    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
        return jsonify({"content": content, "exists": True})
    except IOError:
        return jsonify({"content": "Error reading README.", "exists": False})


@app.route("/api/stats")
def get_stats():
    """Return aggregate dashboard statistics."""
    projects = ProjectTracker.load_all()

    total = len(projects)
    deployed = sum(1 for p in projects if p.get("status") == "deployed")
    destroyed = sum(1 for p in projects if p.get("status") == "destroyed")
    total_cost = sum(float(p.get("estimated_cost", 0)) for p in projects
                     if p.get("status") not in ["destroyed"])
    total_issues = sum(int(p.get("security_issues", 0)) for p in projects
                       if p.get("status") not in ["destroyed"])

    providers = {}
    for p in projects:
        prov = p.get("provider", "Unknown")
        providers[prov] = providers.get(prov, 0) + 1

    return jsonify({
        "total_projects": total,
        "active_deployments": deployed,
        "destroyed": destroyed,
        "total_monthly_cost": round(total_cost, 2),
        "total_security_issues": total_issues,
        "providers": providers,
    })


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  🚀 Terraform AI Agent — Dashboard")
    print("  📍 http://localhost:5000")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)

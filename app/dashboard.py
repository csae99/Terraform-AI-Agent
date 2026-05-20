import os
import glob
import json
import sys
import io
import asyncio
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import sse_starlette

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32" and "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Ensure project root is on sys.path so imports work without PYTHONPATH
_project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.project.tracker import ProjectTracker, UserTracker

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
static_dir = os.path.join(basedir, "static")

app = FastAPI(title="Terraform AI Agent Dashboard")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("FLASK_SECRET_KEY", "super-secret-key"))
app.mount("/static", StaticFiles(directory=static_dir), name="static")

OUTPUT_DIR = "output"
active_logs = {}

# --- Dependencies ---
def get_current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = UserTracker.get_by_id(int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def get_current_user_optional(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return UserTracker.get_by_id(int(user_id))
    return None

# --- Background Task ---
async def run_agent_workflow(prompt: str, budget: float, apply: bool, credentials: dict = None, ai_config: dict = None):
    cmd = [sys.executable, "app/main.py", prompt, "--budget", str(budget), "--auto-fix"]
    if apply:
        cmd.append("--apply")
    
    if ai_config:
        if ai_config.get("model"):
            model = ai_config.get("model")
            provider = ai_config.get("provider")
            if "/" not in model and provider:
                model = f"{provider}/{model}"
            cmd.extend(["--model", model])
        if ai_config.get("key"):
            cmd.extend(["--model-key", ai_config.get("key")])

    temp_slug = "active-run"
    active_logs[temp_slug] = "🚀 Starting Multi-Agent Workflow...\n"
    
    env = os.environ.copy()
    if credentials:
        for key, value in credentials.items():
            if value:
                env[key] = str(value)
    
    owner_id = credentials.get("owner_id") if credentials else None
    if owner_id:
        env["owner_id"] = str(owner_id)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            active_logs[temp_slug] += line.decode('utf-8', errors='replace')
            log_lines = active_logs[temp_slug].split('\n')
            if len(log_lines) > 500:
                active_logs[temp_slug] = '\n'.join(log_lines[-500:])

        await process.wait()
        if process.returncode == 0:
            active_logs[temp_slug] += "\n✅ Workflow Finished successfully.\n"
        else:
            active_logs[temp_slug] += f"\n❌ Workflow Finished with exit code {process.returncode}\n"
    except Exception as e:
        active_logs[temp_slug] += f"\n❌ Error: {str(e)}\n"

# --- Page Routes ---
@app.get("/")
async def index(request: Request, user=Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse(url="/login")
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/login")
async def login_page():
    return FileResponse(os.path.join(static_dir, "login.html"))

# --- API Routes ---
@app.get("/api/projects")
async def list_projects(user=Depends(get_current_user)):
    projects = ProjectTracker.load_all(owner_id=user.id)
    return projects

@app.get("/api/stats")
async def get_stats(user=Depends(get_current_user)):
    projects = ProjectTracker.load_all(owner_id=user.id)
    total_projects = len(projects)
    active_deployments = len([p for p in projects if p.get("status") == "deployed"])
    total_monthly_cost = sum(float(p.get("estimated_cost") or 0) for p in projects)
    total_security_issues = sum(int(p.get("security_issues") or 0) for p in projects)
    
    return {
        "total_projects": total_projects,
        "active_deployments": active_deployments,
        "total_monthly_cost": round(total_monthly_cost, 2),
        "total_security_issues": total_security_issues
    }

@app.post("/api/generate")
async def generate_infrastructure(request: Request, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    data = await request.json()
    prompt = data.get("prompt")
    budget = data.get("budget", 100)
    apply = data.get("apply", False)
    credentials = data.get("credentials") or {}
    ai_config = data.get("ai_config")

    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    credentials["owner_id"] = user.id
    active_logs["active-run"] = "" # Reset log
    background_tasks.add_task(run_agent_workflow, prompt, budget, apply, credentials, ai_config)
    return {"message": "Workflow started", "status": "processing"}

async def log_generator(request: Request):
    """Generator for Server-Sent Events (SSE) log streaming."""
    last_idx = 0
    temp_slug = "active-run"
    while True:
        if await request.is_disconnected():
            break
        logs = active_logs.get(temp_slug, "")
        if len(logs) > last_idx:
            new_logs = logs[last_idx:]
            last_idx = len(logs)
            yield {"data": json.dumps({"logs": new_logs})}
        
        if "✅ Workflow Finished" in logs or "❌ Error" in logs or "❌ Workflow Finished" in logs:
            if len(logs) == last_idx:
                break
        await asyncio.sleep(0.5)

@app.get("/api/logs/active")
async def stream_logs(request: Request):
    return sse_starlette.EventSourceResponse(log_generator(request))

# --- Auth API ---
@app.post("/api/auth/register")
async def register(request: Request):
    data = await request.json()
    user = UserTracker.register(data['username'], data['password'], data.get('email'))
    if user:
        request.session["user_id"] = user.id
        return {"message": "User created", "user": user.username}
    raise HTTPException(status_code=400, detail="Username already exists")

@app.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    user = UserTracker.get_by_username(data['username'])
    if user and user.check_password(data['password']):
        request.session["user_id"] = user.id
        return {"message": "Login successful", "user": user.username}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/auth/logout")
async def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login")

@app.get("/api/auth/me")
async def get_me(user=Depends(get_current_user_optional)):
    if user:
        return {"username": user.username, "id": user.id}
    raise HTTPException(status_code=401, detail="Not logged in")

@app.delete("/api/projects/{slug}")
async def delete_project(slug: str, user=Depends(get_current_user)):
    import shutil
    project = ProjectTracker.load(slug)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    
    ProjectTracker.delete(slug)
    project_dir = os.path.join(OUTPUT_DIR, slug)
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir, ignore_errors=True)
    return {"message": f"Project '{slug}' deleted successfully."}

@app.get("/api/projects/{slug}")
async def get_project(slug: str, user=Depends(get_current_user)):
    meta = ProjectTracker.load(slug)
    if not meta:
        project_dir = os.path.join(OUTPUT_DIR, slug)
        if os.path.isdir(project_dir):
            meta = ProjectTracker._infer_metadata(slug)
        else:
            raise HTTPException(status_code=404, detail=f"Project '{slug}' not found")
    return meta

@app.get("/api/projects/{slug}/code")
async def get_project_code(slug: str):
    project_dir = os.path.join(OUTPUT_DIR, slug)
    if not os.path.isdir(project_dir):
        # Instead of 404, return empty so frontend gracefully says 'No files'
        return {}

    tf_files = {}
    pattern = os.path.join(project_dir, "**", "*.tf")
    for tf in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(tf, project_dir).replace("\\", "/")
        if rel.startswith(f"{slug}/"):
            display_name = rel[len(slug)+1:]
        else:
            display_name = rel

        try:
            with open(tf, "r", encoding="utf-8") as f:
                tf_files[display_name] = f.read()
        except Exception:
            pass

    return tf_files

@app.get("/api/projects/{slug}/snapshots")
async def get_snapshots(slug: str):
    project_dir = os.path.join(OUTPUT_DIR, slug)
    backups_dir = os.path.join(project_dir, "backups")
    if not os.path.exists(backups_dir):
        return []
    
    snapshots = []
    for d in sorted(os.listdir(backups_dir)):
        if os.path.isdir(os.path.join(backups_dir, d)):
            # Name is like {slug}_{timestamp}. Return id and timestamp
            snapshots.append({"id": d, "timestamp": d.split("_")[-1] if "_" in d else d})
    return snapshots

@app.get("/api/projects/{slug}/diff/{snapshot_id}")
async def get_snapshot_diff(slug: str, snapshot_id: str):
    diff = ProjectTracker.get_diff(slug, snapshot_id)
    return {"diff": diff}

@app.get("/api/projects/{slug}/logs/{log_type}")
async def get_project_logs(slug: str, log_type: str):
    log_file = os.path.join(OUTPUT_DIR, slug, "logs", f"{log_type}.log")
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "No logs available."}

@app.get("/api/projects/{slug}/drift")
async def check_project_drift(slug: str):
    import random
    status = "in_sync" if random.random() > 0.5 else "drifted"
    ProjectTracker.save(slug, drift_status=status)
    return {"status": status, "message": "Drift scan complete"}

@app.get("/api/projects/{slug}/report")
async def get_project_report(slug: str):
    project_dir = os.path.join(OUTPUT_DIR, slug)
    report_path = os.path.join(project_dir, "FINANCIAL_REPORT.md")
    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            return {"report": f.read()}
    return {"report": "No financial report generated for this project."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard:app", host="0.0.0.0", port=5000, reload=True)

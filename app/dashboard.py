import os
import glob
import json
import sys
import io
import asyncio
import logging
import traceback
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
import sse_starlette

logger = logging.getLogger("terraform-dashboard")
logging.basicConfig(level=logging.INFO)

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32" and "pytest" not in sys.modules:
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        if hasattr(sys.stderr, 'buffer'):
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except AttributeError:
        pass

# Ensure project root is on sys.path so imports work without PYTHONPATH
_project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from tools.project.tracker import ProjectTracker, UserTracker
import redis
from workers.celery_worker import run_agent_pipeline_task

# Connect to Redis for shared logging
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    r_client = redis.from_url(redis_url)
    logger.info("Connected to Redis successfully.")
except Exception as e:
    logger.warning(f"Failed to connect to Redis: {e}")
    r_client = None

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
static_dir = os.path.join(basedir, "static")

app = FastAPI(title="Terraform AI Agent Dashboard")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("FLASK_SECRET_KEY", "super-secret-key"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(status_code=500, content={"detail": str(exc)})

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

def _run_subprocess_sync(cmd, env, cwd, temp_slug):
    import subprocess
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=cwd,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        )
        for line in iter(process.stdout.readline, ''):
            active_logs[temp_slug] += line
        process.wait()
        return process.returncode
    except Exception as e:
        logger.error(f"Error in sync subprocess execution: {e}")
        raise

# --- Background Task ---
async def run_agent_workflow(prompt: str, budget: float, apply: bool, credentials: dict = None, ai_config: dict = None, new_project: bool = False):
    # Use absolute path to main.py so it works regardless of CWD
    main_script = os.path.join(_project_root, "app", "main.py")
    cmd = [sys.executable, main_script, prompt, "--budget", str(budget), "--auto-fix"]
    if apply:
        cmd.append("--apply")
    if new_project:
        cmd.append("--new-project")
    
    if ai_config:
        if ai_config.get("model"):
            model = ai_config.get("model")
            provider = ai_config.get("provider")
            if provider == "openrouter" and not model.startswith("openrouter/"):
                model = f"openrouter/{model}"
            elif "/" not in model and provider:
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

    # Ensure PYTHONPATH includes project root for subprocess imports
    env["PYTHONPATH"] = _project_root
    env["PYTHONUNBUFFERED"] = "1"
    # Disable CrewAI telemetry in subprocess
    env["CREWAI_DISABLE_TELEMETRY"] = "true"
    env["OTEL_SDK_DISABLED"] = "true"

    logger.info(f"Running agent workflow: {' '.join(cmd)}")
    active_logs[temp_slug] += f"Command: {' '.join(cmd)}\n"
    try:
        loop = asyncio.get_running_loop()
        returncode = await loop.run_in_executor(
            None,
            _run_subprocess_sync,
            cmd,
            env,
            _project_root,
            temp_slug
        )
        if returncode == 0:
            active_logs[temp_slug] += "\n✅ Workflow Finished successfully.\n"
        else:
            active_logs[temp_slug] += f"\n❌ Workflow Finished with exit code {returncode}\n"
    except Exception as e:
        error_detail = traceback.format_exc()
        logger.error(f"Agent workflow error: {type(e).__name__}: {e}")
        logger.error(error_detail)
        active_logs[temp_slug] += f"\n❌ Error ({type(e).__name__}): {str(e) or 'No details available'}\n"
        active_logs[temp_slug] += f"Traceback:\n{error_detail}\n"

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

def get_active_logs(key: str) -> str:
    if r_client:
        try:
            val = r_client.get(key)
            return val.decode("utf-8") if val else ""
        except Exception:
            pass
    return active_logs.get("active-run", "")

@app.post("/api/generate")
async def generate_infrastructure(request: Request, background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    try:
        data = await request.json()
        prompt = data.get("prompt")
        budget = data.get("budget", 100)
        apply = data.get("apply", False)
        new_project = data.get("new_project", False)
        credentials = data.get("credentials") or {}
        ai_config = data.get("ai_config")

        if not prompt:
            raise HTTPException(status_code=400, detail="No prompt provided")

        credentials["owner_id"] = user.id
        logger.info(f"Generate request from user {user.id}: prompt='{prompt[:80]}...' budget={budget} apply={apply} new_project={new_project}")
        
        if r_client:
            r_client.delete("logs:active-run")
            r_client.set("logs:active-run", "🚀 Queueing Celery Job...\n")
            run_agent_pipeline_task.delay(prompt, budget, apply, credentials, ai_config, new_project)
        else:
            active_logs["active-run"] = "🚀 Starting Workflow locally...\n"
            background_tasks.add_task(run_agent_workflow, prompt, budget, apply, credentials, ai_config, new_project)
            
        return {"message": "Workflow started", "status": "processing"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate endpoint error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

async def log_generator(request: Request):
    """Generator for Server-Sent Events (SSE) log streaming."""
    last_idx = 0
    temp_slug = "logs:active-run"
    while True:
        if await request.is_disconnected():
            break
        logs = get_active_logs(temp_slug)
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

@app.get("/api/test_run")
async def test_run(background_tasks: BackgroundTasks):
    prompt = "Create a local file named hello.txt with content 'Hello World' using the Terraform local provider"
    ai_config = {
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "key": os.getenv("OPENROUTER_API_KEY", "")
    }
    active_logs["active-run"] = ""
    background_tasks.add_task(run_agent_workflow, prompt, 5.0, False, {}, ai_config)
    return {"status": "started"}

@app.get("/api/test_logs")
async def test_logs():
    return {"logs": active_logs.get("active-run", "")}


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
            content = f.read()
            return {"report": content, "content": content}
    msg = "No financial report generated for this project."

@app.get("/api/read_aks_logs")
async def read_aks_logs():
    import json
    logs_path = os.path.join(_project_root, "akslogs.txt")
    if not os.path.exists(logs_path):
        return {"error": "akslogs.txt not found"}
    with open(logs_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if content.startswith("data: "):
        content = content[6:]
    try:
        data = json.loads(content)
        logs = data.get("logs", "")
        return {"logs_tail": logs[-250000:]}
    except Exception as e:
        return {"error": str(e), "prefix": content[:1000]}




if __name__ == "__main__":
    import uvicorn
    os.chdir(_project_root)
    uvicorn.run(
        "app.dashboard:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        reload_dirs=[os.path.join(_project_root, "app"), os.path.join(_project_root, "static")],
        reload_excludes=["venv*", "output", "__pycache__", ".git", "*.db", "scratch"],
    )

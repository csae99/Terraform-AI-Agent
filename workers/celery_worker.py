import os
import sys
import subprocess
import redis
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("tasks", broker=redis_url, backend=redis_url)

# Connect to Redis for real-time log publishing
r_client = redis.from_url(redis_url)

@celery_app.task(name="tasks.run_agent_pipeline")
def run_agent_pipeline_task(prompt, budget=100.0, apply=False, credentials=None, ai_config=None, new_project=False):
    # Construct the command exactly like app/dashboard.py
    project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    main_script = os.path.join(project_root, "app", "main.py")
    
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
            
    env = os.environ.copy()
    if credentials:
        for key, value in credentials.items():
            if value is not None:
                env[key] = str(value)
                
    env["PYTHONPATH"] = project_root
    env["PYTHONUNBUFFERED"] = "1"
    env["CREWAI_DISABLE_TELEMETRY"] = "true"
    env["OTEL_SDK_DISABLED"] = "true"
    
    # Check if local cloud emulation (Floci) should be forced
    if os.environ.get("TEST_LOCAL") == "true":
        env["TEST_LOCAL"] = "true"
        
    # Reset the Redis log key
    r_client.delete("logs:active-run")
    r_client.set("logs:active-run", "🚀 [Celery Worker] Starting Pipeline...\n")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=project_root,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace'
        )
        for line in iter(process.stdout.readline, ''):
            r_client.append("logs:active-run", line)
            
        process.wait()
        returncode = process.returncode
        
        if returncode == 0:
            r_client.append("logs:active-run", "\n✅ Workflow Finished successfully.\n")
        else:
            r_client.append("logs:active-run", f"\n❌ Workflow Finished with exit code {returncode}\n")
        return returncode
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        r_client.append("logs:active-run", f"\n❌ Error ({type(e).__name__}): {str(e)}\nTraceback:\n{error_detail}\n")
        raise e

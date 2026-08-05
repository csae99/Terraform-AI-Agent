"""
Celery Tasks – async execution wrappers for the multi-agent pipeline.

Provides workspace isolation, organization context, and execution status tracking.
"""

import os
import shutil
import logging
from celery import Celery
from orchestrator.pipeline import run_full_pipeline
from tools.project.tracker import ProjectTracker

logger = logging.getLogger("celery-tasks")

# Initialize Celery app (pointing to Redis as message broker)
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("terraform_agent_tasks", broker=redis_url, backend=redis_url)

@celery_app.task(bind=True, name="celery_tasks.run_pipeline_async")
def run_pipeline_async(self, prompt: str, budget: float, do_apply: bool, credentials: dict, ai_config: dict, new_project: bool = False, org_id: int = None):
    """
    Asynchronously executes the full Terraform agent pipeline.
    Ensures multi-tenant workspace isolation by setting up a unique working directory.
    
    Args:
        prompt: User natural language requirement.
        budget: Cost budget constraint.
        do_apply: Whether to apply changes to cloud providers.
        credentials: API credentials (AWS/Azure/GCP).
        ai_config: LLM model/key choices.
        new_project: Whether to force a new project slug.
        org_id: Organization context for billing/multi-tenancy.
    """
    task_id = self.request.id
    logger.info(f"[Celery] Started task {task_id} for org {org_id}")
    
    # Establish workspace environment isolation
    workspace_dir = f"workspaces/task-{task_id}"
    os.makedirs(workspace_dir, exist_ok=True)
    
    # Apply credential overrides to environment
    original_env = {}
    for key, value in (credentials or {}).items():
        if value:
            original_env[key] = os.environ.get(key)
            os.environ[key] = str(value)
            
    try:
        # Run pipeline
        result = run_full_pipeline(
            prompt=prompt,
            budget=budget,
            do_apply=do_apply,
            auto_fix=True,
            model_name=ai_config.get("model") if ai_config else None,
            model_key=ai_config.get("key") if ai_config else None,
            owner_id=credentials.get("owner_id") if credentials else None,
            new_project=new_project,
            test_local=os.getenv("TEST_LOCAL") == "true"
        )
        logger.info(f"[Celery] Task {task_id} completed successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"[Celery] Task {task_id} failed: {e}", exc_info=True)
        raise e
    finally:
        # Clean up transient credential environment variables
        for key in (credentials or {}).keys():
            if key in original_env:
                if original_env[key] is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_env[key]
        
        # Workspace cleanup
        try:
            shutil.rmtree(workspace_dir, ignore_errors=True)
        except Exception as cleanup_err:
            logger.warning(f"[Celery] Workspace cleanup error: {cleanup_err}")

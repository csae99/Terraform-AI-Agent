"""
Pipeline – central orchestrator for the multi-agent workflow.

Extracted from app/main.py so that both the CLI entry-point and the
Flask dashboard can invoke the same deterministic pipeline.
"""

import os
import re
from datetime import datetime

from crewai import Crew, Process

from agents import (
    TerraformArchitect,
    TerraformDeveloper,
    SecurityReviewer,
    CostOptimizer,
    DeploymentPlanner,
    TestingAgent,
    GitOpsCoordinator,
)

from workflows.terraform_generation import TerraformGenerationTasks
from workflows.terraform_validation import TerraformValidationTasks
from workflows.terraform_deployment import TerraformDeploymentTasks
from workflows.terraform_testing import TerraformTestingTasks

from tools.security.scanning_tools import SecurityAuditor
from tools.finance.cost_estimation import CostEstimator
from tools.cloud.aws_tools import CloudSync
from tools.terraform.terraform_tools import TerraformTools
from tools.project.tracker import ProjectTracker

from orchestrator.retry_handler import RetryContext, should_retry, _get_pattern_manager
from orchestrator.completeness_validator import (
    validate_workspace_completeness,
    format_completeness_report,
)


# ── Helper utilities ─────────────────────────────────────────────────

import uuid
import re

def get_project_slug(architect_output: str, prompt: str = "") -> str:
    """Extract a URL-friendly slug from the architect's output."""
    # Handle possible markdown bolding, spaces/underscores, and case insensitivity
    match = re.search(r"\*?\*?project[_\s]slug\*?\*?:?\*?\*?\s*([^\n\r]+)", architect_output, re.IGNORECASE)
    if match:
        name = match.group(1).replace("*", "").strip()
        slug = name.lower().replace(" ", "-").replace("_", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        if slug:
            return slug
    
    # Fallback: extract the first 3 meaningful words from the prompt
    if prompt:
        generic = {"create", "make", "build", "generate", "terraform", "configuration", "infrastructure", "production", "valid", "code", "the", "a", "an", "for", "with", "using", "setup", "deploy", "provision"}
        words = [w for w in re.sub(r'[^a-zA-Z0-9\s]', '', prompt).lower().split() if len(w) > 2 and w not in generic]
        if words:
            return "-".join(words[:3])
            
    # Ultimate fallback if LLM completely failed and no prompt
    short_id = str(uuid.uuid4())[:8]
    return f"aws-infrastructure-{short_id}"


def extract_mermaid(text: str) -> str:
    """Extract mermaid code block from text."""
    pattern = r"```mermaid\s+(.*?)\s+```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def inject_floci_overrides(slug: str):
    """Write a providers_override.tf file to force Terraform to use local Floci emulated endpoints."""
    output_base = os.path.join("output", slug)
    if not os.path.exists(output_base):
        os.makedirs(output_base)
        
    is_in_docker = os.path.exists('/.dockerenv') or os.environ.get("RUNNING_IN_DOCKER") == "true"
    floci_host = "floci" if is_in_docker else "localhost"
    floci_endpoint = f"http://{floci_host}:4566"
    
    override_content = f"""
provider "aws" {{
  region                      = "us-east-1"
  access_key                  = "mock_access_key"
  secret_key                  = "mock_secret_key"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true
  endpoints {{
    apigateway     = "{floci_endpoint}"
    apigatewayv2   = "{floci_endpoint}"
    autoscaling    = "{floci_endpoint}"
    cloudformation = "{floci_endpoint}"
    cloudfront     = "{floci_endpoint}"
    cloudwatch     = "{floci_endpoint}"
    cognitoidp     = "{floci_endpoint}"
    cognitoidentity= "{floci_endpoint}"
    dynamodb       = "{floci_endpoint}"
    ec2            = "{floci_endpoint}"
    ecs            = "{floci_endpoint}"
    eks            = "{floci_endpoint}"
    elasticsearch  = "{floci_endpoint}"
    firehose       = "{floci_endpoint}"
    iam            = "{floci_endpoint}"
    kinesis        = "{floci_endpoint}"
    kms            = "{floci_endpoint}"
    lambda         = "{floci_endpoint}"
    redshift       = "{floci_endpoint}"
    route53        = "{floci_endpoint}"
    s3             = "{floci_endpoint}"
    secretsmanager = "{floci_endpoint}"
    ses            = "{floci_endpoint}"
    sns            = "{floci_endpoint}"
    sqs            = "{floci_endpoint}"
    ssm            = "{floci_endpoint}"
    stepfunctions  = "{floci_endpoint}"
    sts            = "{floci_endpoint}"
  }}
}}
"""
    override_path = os.path.join(output_base, "providers_override.tf")
    with open(override_path, "w") as f:
        f.write(override_content)
    print(f"[Local Test] Injected Floci overrides at {override_path}")


# ── Main Pipeline ────────────────────────────────────────────────────

def run_full_pipeline(
    prompt: str,
    budget: float = 100.0,
    do_apply: bool = False,
    auto_fix: bool = False,
    model_name: str = None,
    model_key: str = None,
    owner_id: str = None,
    org_id: int = None,
    new_project: bool = False,
    cli_flags: list = None,
    test_local: bool = False,
    gitops: bool = False,
    git_repo: str = None,
    git_token: str = None,
    target_branch: str = "main",
) -> dict:
    """Execute the full multi-agent Terraform pipeline.

    This is the single authoritative entry-point for both the CLI
    (``app/main.py``) and the web dashboard (``app/dashboard.py``).

    Returns:
        dict with keys: slug, status, estimated_cost, security_issues
    """
    import time as _time_perf
    start_time = _time_perf.time()
    is_test_local = test_local or os.environ.get("TEST_LOCAL") == "true" or "--test-local" in (cli_flags or [])
    is_gitops = gitops or os.environ.get("GITOPS") == "true" or "--gitops" in (cli_flags or [])
    git_repo_target = git_repo or os.environ.get("GIT_REPO")
    git_token_target = git_token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GIT_TOKEN")
    git_base_branch = target_branch or os.environ.get("GIT_TARGET_BRANCH") or "main"

    if not org_id and os.environ.get("org_id"):
        try:
            org_id = int(os.environ.get("org_id"))
        except ValueError:
            pass

    if cli_flags is None:
        cli_flags = []

    print("\n" + "=" * 50)
    print("      Universal AI Agent - Phase 7 (Visualizer Platform)")
    print("=" * 50 + "\n")

    # ── Instantiate agent classes ────────────────────────────────
    architect_agent_cls = TerraformArchitect(model_name=model_name, api_key=model_key)
    developer_agent_cls = TerraformDeveloper(model_name=model_name, api_key=model_key)
    auditor_agent_cls = SecurityReviewer(model_name=model_name, api_key=model_key)
    finops_agent_cls = CostOptimizer(model_name=model_name, api_key=model_key)
    deployer_agent_cls = DeploymentPlanner(model_name=model_name, api_key=model_key)
    testing_agent_cls = TestingAgent(model_name=model_name, api_key=model_key)

    auditor = SecurityAuditor()
    estimator = CostEstimator()
    cloud = CloudSync()

    # ── 1. Cloud Readiness & Architecture ────────────────────────
    readiness = cloud.check_cloud_readiness()
    detected_provider = readiness["provider"]
    print(f"Cloud Readiness: {detected_provider} Ready")

    architect_agent = architect_agent_cls.get_agent()
    arch_task = TerraformGenerationTasks.design_architecture_task(architect_agent, prompt)

    crew_arch = Crew(agents=[architect_agent], tasks=[arch_task], verbose=True)
    arch_result = str(crew_arch.kickoff())

    print("\n⏳ Cooling down for 10 seconds to prevent rate limits...")
    import time
    time.sleep(10)

    slug = get_project_slug(arch_result, prompt)
    base_slug = slug
    if new_project:
        counter = 1
        while ProjectTracker.load(slug) is not None or os.path.exists(os.path.join("output", slug)):
            slug = f"{base_slug}-{counter}"
            counter += 1
    # Replace references to the base slug in the architecture design document with the actual slug
    if slug != base_slug:
        arch_result = re.sub(re.escape(base_slug), slug, arch_result, flags=re.IGNORECASE)
    mermaid_diagram = extract_mermaid(arch_result)
    output_base = os.path.join("output", slug)
    os.makedirs(output_base, exist_ok=True)
    print(f"\nBuilding Project Workspace: {output_base}/")

    # ── Track project from the start ─────────────────────────────
    ProjectTracker.save(
        slug,
        prompt=prompt,
        status="generating",
        budget=budget,
        provider=detected_provider,
        flags=cli_flags,
        mermaid_diagram=mermaid_diagram,
        owner_id=owner_id,
        org_id=org_id,
        healing_rounds_taken=1,
        run_duration=0.0,
        errors_encountered=[],
        patterns_applied=[],
        qa_report=""
    )

    # ── 2. Development & Audit Loop (self-healing) ───────────────
    retry = RetryContext(max_rounds=3)
    retry.record_decision("pipeline_started")
    is_deployed = False

    while retry.has_retries_left:
        print(f"\n--- Round {retry.current_round}: Development & Audit ---")
        retry.record_decision(f"round_{retry.current_round}_started")

        developer_agent = developer_agent_cls.get_agent()
        auditor_agent = auditor_agent_cls.get_agent()
        finops_agent = finops_agent_cls.get_agent()
        deployer_agent = deployer_agent_cls.get_agent()
        testing_agent = testing_agent_cls.get_agent()

        # Check if we have previous errors/advice to inject
        error_guidance = ""
        if retry.current_round > 1 and retry.errors:
            latest_error = retry.errors[-1]
            error_guidance = TerraformValidationTasks.build_error_context(latest_error)
            if retry.advice:
                error_guidance += f"\nAdvice from pattern memory:\n{retry.advice}"
            if hasattr(retry, "reflection_advice") and retry.reflection_advice:
                ref = retry.reflection_advice
                error_guidance += (
                    f"\n🔬 Dynamic Reflection Debugging Analysis:\n"
                    f"  - Cause of Error: {ref.get('cause')}\n"
                    f"  - Fix Instructions: {ref.get('fix_advice')}\n"
                    f"  - Correct HCL Template Snippet:\n{ref.get('corrected_snippet')}\n"
                )

        dev_task = TerraformGenerationTasks.write_terraform_task(
            developer_agent, slug, arch_result, error_guidance=error_guidance
        )
        audit_task = TerraformValidationTasks.audit_task(auditor_agent, slug)
        cost_task = TerraformValidationTasks.financial_analysis_task(
            finops_agent, slug, budget
        )
        deploy_task = (
            TerraformDeploymentTasks.deployment_task(deployer_agent, slug)
            if do_apply
            else None
        )
        testing_task = (
            TerraformTestingTasks.behavior_testing_task(testing_agent, slug)
            if do_apply
            else None
        )

        active_tasks = [dev_task, audit_task, cost_task]
        active_agents = [developer_agent, auditor_agent, finops_agent]

        if deploy_task:
            active_tasks.append(deploy_task)
            active_agents.append(deployer_agent)

        if testing_task:
            active_tasks.append(testing_task)
            active_agents.append(testing_agent)

        crew_dev = Crew(
            agents=active_agents,
            tasks=active_tasks,
            process=Process.sequential,
            verbose=True,
        )

        # ── Crew kickoff with rate-limit-aware retry ─────────────
        import re as _re
        import time as _time_sleep
        MAX_CREW_RETRIES = 3
        crew_result = None
        crew_succeeded = False

        for crew_attempt in range(1, MAX_CREW_RETRIES + 1):
            try:
                crew_result = str(crew_dev.kickoff())
                retry.record_decision("fix_applied")
                # Fallback: Extract and write files from the developer's output if tools were not called
                if dev_task.output and dev_task.output.raw:
                    extracted = TerraformTools.extract_and_write_files_from_text(dev_task.output.raw, slug)
                    if extracted:
                        print(f"Fallback Extractor: Successfully extracted and wrote {len(extracted)} files from Developer response: {extracted}")
                crew_succeeded = True
                break
            except Exception as e:
                error_str = str(e)
                error_lower = error_str.lower()
                is_rate_limit = any(kw in error_lower for kw in [
                    "429", "quota", "exhausted", "rate", "resource_exhausted",
                    "rate-limited", "limit", "too many requests"
                ])

                if is_rate_limit and crew_attempt < MAX_CREW_RETRIES:
                    # Parse exact wait time from Google's error response
                    wait_time = 30  # safe default
                    match_secs = _re.search(r"retry\s+in\s+([\d\.]+)\s*s", error_lower)
                    match_delay = _re.search(r"['\"]retryDelay['\"]\s*:\s*['\"](\d+)s?['\"]", error_lower)
                    if match_secs:
                        wait_time = float(match_secs.group(1)) + 2.0
                    elif match_delay:
                        wait_time = float(match_delay.group(1)) + 2.0

                    print(f"\n⏳ [Rate Limit] Crew attempt {crew_attempt}/{MAX_CREW_RETRIES} hit rate limit. "
                          f"Waiting {wait_time:.1f}s before retrying...")
                    retry.record_decision(f"crew_rate_limited_attempt_{crew_attempt}")
                    _time_sleep.sleep(wait_time)

                    # Recreate crew for a fresh kickoff (CrewAI doesn't support re-kicking a failed crew)
                    developer_agent = developer_agent_cls.get_agent()
                    dev_task = TerraformGenerationTasks.write_terraform_task(
                        developer_agent, slug, arch_result, error_guidance
                    )
                    active_tasks = [dev_task, audit_task, cost_task]
                    active_agents = [developer_agent, auditor_agent, finops_agent]
                    if deploy_task:
                        deployer_agent = deployer_agent_cls.get_agent()
                        deploy_task = TerraformDeploymentTasks.deployment_task(deployer_agent, slug)
                        active_tasks.append(deploy_task)
                        active_agents.append(deployer_agent)
                    if testing_task:
                        testing_agent = testing_agent_cls.get_agent()
                        testing_task = TerraformTestingTasks.behavior_testing_task(testing_agent, slug)
                        active_tasks.append(testing_task)
                        active_agents.append(testing_agent)
                    crew_dev = Crew(
                        agents=active_agents,
                        tasks=active_tasks,
                        process=Process.sequential,
                        verbose=True,
                    )
                    continue
                else:
                    # Non-rate-limit error or exhausted retries — fail permanently
                    print(f"\n[!] Developer Crew failed with error: {error_str}")
                    retry.record_decision("crew_execution_failed")
                    run_duration = _time_perf.time() - start_time
                    ProjectTracker.save(
                        slug,
                        status="failed",
                        healing_rounds_taken=retry.current_round,
                        run_duration=round(run_duration, 2),
                        errors_encountered=retry.errors + [f"Crew execution failed: {error_str}"],
                        reflection_advice=getattr(retry, "reflection_advice", None),
                        decision_trace=retry.decision_trace
                    )
                    return {
                        "slug": slug,
                        "status": "failed",
                        "estimated_cost": "0.00",
                        "security_issues": 0,
                    }

        if not crew_succeeded:
            print(f"\n[!] Developer Crew failed after {MAX_CREW_RETRIES} rate-limit retries.")
            retry.record_decision("crew_execution_failed_after_retries")
            run_duration = _time_perf.time() - start_time
            ProjectTracker.save(
                slug,
                status="failed",
                healing_rounds_taken=retry.current_round,
                run_duration=round(run_duration, 2),
                errors_encountered=retry.errors + ["Crew failed: rate limit retries exhausted"],
                reflection_advice=getattr(retry, "reflection_advice", None),
                decision_trace=retry.decision_trace
            )
            return {
                "slug": slug,
                "status": "failed",
                "estimated_cost": "0.00",
                "security_issues": 0,
            }

        # ── Completeness check & focused retry ────────────────────
        import time as _time
        MAX_COMPLETION_RETRIES = 2
        for completion_attempt in range(MAX_COMPLETION_RETRIES):
            completeness = validate_workspace_completeness(slug, arch_result)
            print(format_completeness_report(completeness))

            if completeness["is_complete"]:
                print("✅ Workspace is complete. Proceeding to validation.")
                break

            print(f"\n🔄 Completion Retry {completion_attempt + 1}/{MAX_COMPLETION_RETRIES}: "
                  f"Running focused completion task for missing files...")

            # Cooldown to avoid rate limits
            print("⏳ Cooling down for 10 seconds before completion retry...")
            _time.sleep(10)

            try:
                # Re-create the developer agent for the completion task
                completion_dev_agent = developer_agent_cls.get_agent()
                completion_task = TerraformGenerationTasks.complete_missing_files_task(
                    completion_dev_agent, slug, arch_result, completeness
                )
                completion_crew = Crew(
                    agents=[completion_dev_agent],
                    tasks=[completion_task],
                    process=Process.sequential,
                    verbose=True,
                )
                completion_crew.kickoff()
                # Fallback: Extract and write files from the completion response if tools were not called
                if completion_task.output and completion_task.output.raw:
                    extracted = TerraformTools.extract_and_write_files_from_text(completion_task.output.raw, slug)
                    if extracted:
                        print(f"Fallback Extractor: Successfully extracted and wrote {len(extracted)} files from Completion response: {extracted}")
            except Exception as comp_err:
                print(f"\n[!] Completion retry {completion_attempt + 1} failed: {comp_err}")
        else:
            # Exhausted completion retries - log but continue to validation anyway
            final_check = validate_workspace_completeness(slug, arch_result)
            if not final_check["is_complete"]:
                print("\n⚠️  WARNING: Workspace is still incomplete after all completion retries.")
                print(format_completeness_report(final_check))
                print("Proceeding to validation anyway...")

        if is_test_local:
            inject_floci_overrides(slug)

        # ── Security analysis for self-healing ───────────────────
        audit_results = auditor.run_comprehensive_scan(output_base)
        
        # Ensure terraform is syntactically valid before considering this round a success
        val_result = TerraformTools._validate_terraform_code(slug)
        if "Failed" in val_result:
            retry.record_decision("terraform_validation_failed")
            if should_retry(val_result):
                print(f"\n[!] Terraform Validation Failed. Retrying...")
                
                # Enforce Priority Routing:
                # 1. Trusted matches first (no reflection)
                # 2. Candidate matches second (no reflection)
                # 3. Dynamic reflection fallback if no hits or if previous round failed
                pm = _get_pattern_manager()
                trusted_hits = []
                candidate_hits = []
                if pm:
                    trusted_hits = pm.match_trusted(val_result)
                    candidate_hits = pm.match_candidates(val_result)
                
                has_pattern = bool(trusted_hits or candidate_hits)
                trigger_reflection = not has_pattern
                
                if trigger_reflection:
                    print("\n🔬 No static failure pattern matched. Triggering LLM Reflection...")
                    retry.record_decision("reflection_triggered")
                    retry.record_decision("search_triggered")
                    from orchestrator.reflection import reflect_on_error
                    ref_advice = reflect_on_error(val_result, slug)
                    if ref_advice:
                        retry.reflection_advice = ref_advice
                        print(f"✅ Reflection Generated Advice: {ref_advice['fix_advice']}")
                else:
                    retry.reflection_advice = None
                    if trusted_hits:
                        print(f"[Priority Routing] Matched Trusted Pattern(s): {[h['error_substring'] for h in trusted_hits]}")
                        retry.record_decision("trusted_pattern_matched")
                    elif candidate_hits:
                        print(f"[Priority Routing] Matched Candidate Pattern(s): {[h['error_substring'] for h in candidate_hits]}")
                        retry.record_decision("candidate_pattern_matched")
                
                retry.record_errors(f"Terraform validation failed: {val_result}")
                retry.advance()
                continue
            else:
                print("\n[!] Hard stop or max retries reached. Validation failed.")
                retry.record_decision("validation_failed")
                retry.record_errors(f"Terraform validation failed (hard stop): {val_result}")
                break
        else:
            retry.record_decision("terraform_validation_succeeded")
                
        findings = audit_results.get("findings", [])
        critical_count = len(
            [f for f in findings if f.get("severity") in ["CRITICAL", "HIGH"]]
        )
        if critical_count > 0:
            retry.record_decision("security_audit_failed")
        else:
            retry.record_decision("security_audit_succeeded")

        # Track best state
        if retry.best_finding_count is None or critical_count < retry.best_finding_count:
            retry.best_finding_count = critical_count
            backup_result = TerraformTools._backup_workspace(slug)
            if "Backup created at " in backup_result:
                retry.best_backup = backup_result.split("Backup created at ")[1].strip()
                print(
                    f"  📸 Snapshot saved (best so far: {retry.best_finding_count} issues)"
                )

        # Check deployment success
        is_deployed = True
        if do_apply:
            if deploy_task and hasattr(deploy_task, "output") and deploy_task.output:
                is_deployed = "🚀 Deployment Successful!" in str(deploy_task.output.raw)
            else:
                log_path = os.path.join(output_base, "logs", "terraform_apply.log")
                if os.path.exists(log_path):
                    try:
                        with open(log_path, "r", encoding="utf-8") as f:
                            apply_log = f.read()
                        is_deployed = "Apply complete!" in apply_log
                    except Exception as e:
                        print(f"[Deployment Check] Warning: failed to read apply log: {e}")
                        is_deployed = False
                else:
                    is_deployed = False
            
            if is_deployed:
                retry.record_decision("deployment_succeeded")
            else:
                retry.record_decision("deployment_failed")

        if critical_count == 0 and is_deployed:
            print(
                "\n✅ Verification SUCCESS! No security issues and deployment is live."
            )
            retry.record_decision("fix_succeeded")
            if retry.current_round > 1:
                main_tf_path = os.path.join(output_base, "main.tf")
                fix_applied_content = ""
                if os.path.exists(main_tf_path):
                    try:
                        with open(main_tf_path, "r", encoding="utf-8") as f:
                            fix_applied_content = f.read()
                    except Exception as e:
                        print(f"[Self-Learning] Warning: failed to read {main_tf_path}: {e}")
                
                pm = _get_pattern_manager()
                if pm:
                    print(f"[Self-Learning] Run succeeded in round {retry.current_round}. Calling pattern_manager.learn_from_run...")
                    pm.learn_from_run(
                        error_logs="\n".join(retry.errors),
                        fix_applied=fix_applied_content
                    )
            break

        # ── Record errors & enrich with pattern advice ───────────
        error_summary = ""
        if critical_count > 0:
            error_summary += f"Security audit failed:\n{auditor.format_report(audit_results)}\n"
        if not is_deployed:
            error_summary += f"Deployment failed. Raw output:\n{crew_result}\n"
        
        if not error_summary:
            error_summary = f"Round {retry.current_round}: Verification failed for unknown reasons."

        # Decay pattern confidence if we had a match for the error but it failed to heal
        pm = _get_pattern_manager()
        has_pattern = False
        if pm:
            trusted_hits = pm.match_trusted(error_summary)
            candidate_hits = pm.match_candidates(error_summary)
            hits = trusted_hits + candidate_hits
            if hits:
                has_pattern = True
                for p in hits:
                    pm.decay_pattern(p["error_substring"])
                if trusted_hits:
                    retry.record_decision("trusted_pattern_matched")
                else:
                    retry.record_decision("candidate_pattern_matched")
                    
        if not has_pattern:
            print("\n🔬 No static failure pattern matched. Triggering LLM Reflection...")
            retry.record_decision("reflection_triggered")
            retry.record_decision("search_triggered")
            from orchestrator.reflection import reflect_on_error
            ref_advice = reflect_on_error(error_summary, slug)
            if ref_advice:
                retry.reflection_advice = ref_advice
                print(f"✅ Reflection Generated Advice: {ref_advice['fix_advice']}")
        else:
            retry.reflection_advice = None

        retry.record_errors(error_summary)

        if retry.current_round < retry.max_rounds:
            if auto_fix:
                print(
                    f"\n🤖 Auto-Fix Enabled: Proceeding to Round {retry.current_round + 1}..."
                )
            else:
                choice = input(
                    f"\nWould you like to proceed with autonomous Fix Round "
                    f"{retry.current_round + 1}? [y/n]: "
                ).lower()
                if choice != "y":
                    break

            retry.advance()
        else:
            print("\n❌ Max rounds reached.")
            break

    # ── 3. Revert Logic ──────────────────────────────────────────
    if (
        retry.best_finding_count
        and retry.best_finding_count > 0
        and retry.best_backup
    ):
        print(
            f"\n[WARNING] Project has {retry.best_finding_count} unresolved high-severity issues."
        )
        if auto_fix:
            print("🤖 Auto-Fix Enabled: Automatically reverting to best-known state.")
            revert_choice = "y"
        else:
            revert_choice = input(
                "Would you like to REVERT to the best-known state? (Recommended) [y/n]: "
            ).lower()

        if revert_choice == "y":
            retry.record_decision("revert_triggered")
            TerraformTools._restore_workspace(slug, retry.best_backup)
            print(
                f"Workspace reverted to best-known version with "
                f"{retry.best_finding_count} issues."
            )

    # ── 4. Final FinOps Report ───────────────────────────────────
    print("\nFinalizing Project Reports...")
    cost_results = estimator._execute_infracost(output_base)

    report_path = os.path.join(output_base, "FINANCIAL_REPORT.md")
    if not os.path.exists(report_path):
        print(f"Fallback cost report: Generating FINANCIAL_REPORT.md dynamically at {report_path}...")
        try:
            report_content = estimator._build_markdown_report(cost_results, budget)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
        except Exception as e:
            print(f"Fallback cost report generation failed: {e}")

    total_cost = float(cost_results.get("total_monthly_cost", 0))
    budget_status = (
        "✅ WITHIN BUDGET" if total_cost <= budget else "❌ OVER BUDGET"
    )

    final_status = "deployed" if (do_apply and is_deployed) else "generated"
    final_security = (
        retry.best_finding_count if retry.best_finding_count is not None else 0
    )

    # ── 5. GitOps Branching & Pull Request Automation ────────────
    pr_url = None
    pr_number = None
    pr_status = "none"
    approval_status = "none"
    git_branch_name = None

    if is_gitops and git_repo_target:
        print("\n" + "=" * 50)
        print("         🔀 GITOPS RELEASE & PR COORDINATION")
        print("=" * 50)
        branch_res = GitOpsTools.create_feature_branch(output_base, slug, base_branch=git_base_branch)
        git_branch_name = branch_res.get("branch_name", f"ai/{slug}")
        print(f"Created Git Feature Branch: {git_branch_name}")

        commit_res = GitOpsTools.commit_files(output_base, slug, prompt)
        print(f"Committed IaC Files: {commit_res.get('commit_message', '')}")

        push_res = GitOpsTools.push_branch(output_base, git_repo_target, git_branch_name, git_token_target)
        if push_res.get("success"):
            print(f"Pushed branch to remote repository: {git_repo_target}")
        else:
            print(f"Warning: Git push returned: {push_res.get('error')}")

        pr_body = GitOpsTools.generate_pr_body(
            slug=slug,
            prompt=prompt,
            arch_result=arch_result,
            cost_summary=estimator.format_report(cost_results),
            audit_summary=auditor.format_report(audit_results),
            mermaid_diagram=mermaid_diagram
        )

        pr_res = GitOpsTools.create_pull_request(
            repo_url=git_repo_target,
            branch_name=git_branch_name,
            target_branch=git_base_branch,
            title=f"feat(iac): provision {slug}",
            body=pr_body,
            token=git_token_target
        )

        if pr_res.get("success"):
            pr_url = pr_res.get("pr_url")
            pr_number = pr_res.get("pr_number")
            pr_status = "open"
            approval_status = "pending"
            final_status = "pr_opened"
            print(f"✅ Pull Request Opened: {pr_url} (PR #{pr_number})")
            print(f"🔒 Approval Status: PENDING (Requires Org Owner/Admin Approval)")

            # Record Audit Trail
            AuditTracker.log_action(
                action="gitops_pr_created",
                user_id=owner_id,
                org_id=org_id,
                resource_slug=slug,
                details=f"Opened Pull Request #{pr_number} on {git_repo_target} (Branch: {git_branch_name})"
            )
        else:
            print(f"❌ Failed to open Pull Request: {pr_res.get('error')}")

    # ── Gather Telemetry ──────────────────────────────────────────
    run_duration = _time_perf.time() - start_time
    qa_report = ""
    if do_apply and 'testing_task' in locals() and testing_task and hasattr(testing_task, "output") and testing_task.output:
        qa_report = str(testing_task.output.raw)

    retry.record_decision("pipeline_completed")

    ProjectTracker.save(
        slug,
        prompt=prompt,
        status=final_status,
        budget=budget,
        estimated_cost=total_cost,
        security_issues=final_security,
        provider=detected_provider,
        flags=cli_flags,
        mermaid_diagram=mermaid_diagram,
        owner_id=owner_id,
        org_id=org_id,
        healing_rounds_taken=retry.current_round,
        run_duration=round(run_duration, 2),
        errors_encountered=retry.errors,
        patterns_applied=retry.patterns_applied,
        qa_report=qa_report,
        reflection_advice=getattr(retry, "reflection_advice", None),
        decision_trace=retry.decision_trace,
        git_repo=git_repo_target if is_gitops else None,
        git_branch=git_branch_name,
        pr_url=pr_url,
        pr_number=pr_number,
        pr_status=pr_status,
        approval_status=approval_status
    )

    print("\n" + "=" * 50)
    print("                FINAL AGENT REPORTS")
    print("=" * 50)
    print(f"BUDGET STATUS: {budget_status} (Limit: ${budget})")
    print(estimator.format_report(cost_results))
    print("=" * 50)

    print(f"\nWorkflow complete! Final output at: output/{slug}/")
    print("📊 Dashboard: python dashboard.py  →  http://localhost:5000")

    return {
        "slug": slug,
        "status": final_status,
        "estimated_cost": total_cost,
        "security_issues": final_security,
    }


# ── Destroy helper ───────────────────────────────────────────────────

def run_destroy_pipeline(slug: str, model_name: str = None, model_key: str = None):
    """Destroy an existing workspace."""
    print(f"\n☢️  DESTRUCTIVE ACTION: Destroying workspace '{slug}'")
    decom_agent_cls = DeploymentPlanner(model_name=model_name, api_key=model_key)
    decom_agent = decom_agent_cls.get_agent()
    decom_task = TerraformDeploymentTasks.decommissioning_task(decom_agent, slug)
    crew_decom = Crew(agents=[decom_agent], tasks=[decom_task], verbose=True)
    crew_decom.kickoff()
    ProjectTracker.save(slug, status="destroyed")
    print(f"\n✅ Infrastructure Destroyed for {slug}")

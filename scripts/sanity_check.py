"""
Sanity Check Utility for Terraform AI Agent Platform.
Executes a rapid, lightweight health assessment across all subsystems:
1. Python Environment & Core Dependencies
2. Database ORM & RBAC Integrity
3. IaC Engine & Binary Discovery
4. Governance, Policy-as-Code & Risk Matrix
5. Kubernetes Control Plane & CRD Readiness (Phase 15)
6. Web Gateway & REST API Readiness

Usage:
    python scripts/sanity_check.py
"""

import os
import sys
import time
import io
import traceback
from typing import List, Tuple

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force UTF-8 encoding for console output on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'buffer') and getattr(sys.stdout, 'encoding', '').lower() != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'buffer') and getattr(sys.stderr, 'encoding', '').lower() != 'utf-8':
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_banner():
    print(f"\n{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}[*] TERRAFORM AI AGENT -- SYSTEM SANITY CHECK{Colors.RESET}")
    print(f"{Colors.CYAN}Fast validation of core runtime, engine, database, and control plane.{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}\n")


def check_python_and_dependencies() -> Tuple[bool, str]:
    """Check 1: Verify Python runtime and critical package imports."""
    if sys.version_info < (3, 9):
        return False, f"Python 3.9+ required, found {sys.version.split()[0]}"

    required_modules = [
        "pydantic",
        "fastapi",
        "uvicorn",
        "yaml",
        "sqlalchemy",
        "requests",
    ]
    missing = []
    for mod in required_modules:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)

    if missing:
        return False, f"Missing required modules: {', '.join(missing)}"
    return True, f"Python {sys.version.split()[0]} with all core packages loaded."


def check_database_and_rbac() -> Tuple[bool, str]:
    """Check 2: Verify SQLite / PostgreSQL connection and User/Org models."""
    from tools.project.tracker import UserModel, OrganizationModel, SessionLocal

    session = SessionLocal()
    try:
        user_count = session.query(UserModel).count()
        org_count = session.query(OrganizationModel).count()
        return True, f"DB session active ({user_count} users, {org_count} organizations recorded in database)."
    except Exception as e:
        return False, f"Database error: {str(e)}"
    finally:
        session.close()


def check_iac_engine_and_binaries() -> Tuple[bool, str]:
    """Check 3: Verify IaC Engine factory and local security/pricing binaries."""
    from tools.engine.factory import EngineFactory

    engine = EngineFactory.get_engine("opentofu")
    bin_name = engine.name

    # Check for tfsec and infracost executables in workspace
    tfsec_path = os.path.join(PROJECT_ROOT, "tfsec.exe")
    infracost_path = os.path.join(PROJECT_ROOT, "infracost.exe")

    bin_status = []
    bin_status.append(f"IaC: {bin_name}")
    bin_status.append(f"tfsec: {'present' if os.path.exists(tfsec_path) else 'docker-fallback'}")
    bin_status.append(f"infracost: {'present' if os.path.exists(infracost_path) else 'docker-fallback'}")

    return True, ", ".join(bin_status)


def check_governance_and_risk() -> Tuple[bool, str]:
    """Check 4: Verify Policy-as-Code (OPA) and 5D Risk Matrix."""
    from policy.opa_engine import OPAEngine
    from portal.agent_governance import AgentGovernanceFramework

    # Test OPA evaluation with mock code
    mock_hcl = 'resource "aws_s3_bucket" "test" { bucket = "my-bucket" }'
    opa_res = OPAEngine.evaluate_compliance(mock_hcl, pack="soc2")

    # Test risk score calculation
    risk_assessment = AgentGovernanceFramework.calculate_risk_score(
        hcl_code=mock_hcl,
        estimated_cost=120.0,
        environment="staging",
    )

    score = risk_assessment.get("composite_risk_score", 0.0)
    level = risk_assessment.get("risk_level", "UNKNOWN")
    return True, f"OPA engine ready (compliance: {opa_res.get('allow')}); Risk evaluator: score {score}/100 ({level})."


def check_k8s_control_plane() -> Tuple[bool, str]:
    """Check 5: Verify Phase 15 CRD schemas, reconciler, and ArgoCD health evaluator."""
    from k8s.operator.crd_schema import TerraformAgentResource
    from k8s.operator.reconciler import AgentReconciler
    from k8s.gitops.argocd_plugin import evaluate_argocd_health

    # 1. Verify CRD definitions on disk
    crds_dir = os.path.join(PROJECT_ROOT, "k8s", "crds")
    expected_crds = [
        "platform.terraform-ai.io_terraformagents.yaml",
        "platform.terraform-ai.io_platformprojects.yaml",
        "platform.terraform-ai.io_workflows.yaml",
        "platform.terraform-ai.io_policies.yaml",
    ]
    for crd in expected_crds:
        if not os.path.exists(os.path.join(crds_dir, crd)):
            return False, f"Missing CRD definition: {crd}"

    # 2. Test Pydantic model validation & reconciliation
    res = TerraformAgentResource.model_validate({
        "metadata": {"name": "sanity-agent", "namespace": "default"},
        "spec": {"prompt": "Sanity check S3 bucket", "environment": "dev", "engine": "opentofu"},
    })
    reconciler = AgentReconciler()
    result = reconciler.reconcile(res)
    if not result.get("success"):
        return False, f"Reconciler cycle failed: {result.get('error')}"

    # 3. Test ArgoCD health check mapping
    health = evaluate_argocd_health({"phase": res.status.phase})
    if health.get("status") != "Healthy":
        return False, f"ArgoCD health mismatch: expected Healthy, got {health.get('status')}"

    return True, f"4 CRDs valid, Reconciler lifecycle OK, ArgoCD health mapped to '{health.get('status')}'."


def check_web_gateway_and_api() -> Tuple[bool, str]:
    """Check 6: Verify FastAPI routes and readiness probes."""
    from fastapi.testclient import TestClient
    from app.dashboard import app

    client = TestClient(app)

    # Probe 1: K8s operator status
    resp_k8s = client.get("/api/k8s/operator/status")
    if resp_k8s.status_code != 200 or resp_k8s.json().get("status") != "Healthy":
        return False, f"/api/k8s/operator/status returned code {resp_k8s.status_code}"

    # Probe 2: CRDs list
    resp_crds = client.get("/api/k8s/crds")
    if resp_crds.status_code != 200 or resp_crds.json().get("count") != 4:
        return False, f"/api/k8s/crds returned code {resp_crds.status_code}"

    # Probe 3: Manifest generator (POST route)
    resp_gen = client.post("/api/k8s/manifest/generate", json={"name": "sanity-check", "prompt": "Web tier on AWS"})
    if resp_gen.status_code != 200 or "manifest" not in resp_gen.json():
        return False, f"/api/k8s/manifest/generate returned code {resp_gen.status_code}"

    return True, "FastAPI gateway responsive; /api/k8s/* GET and POST probes returned HTTP 200."


def run_all_sanity_checks() -> bool:
    """Executes all checks sequentially and renders formatted results."""
    print_banner()

    checks = [
        ("Core Environment & Python Dependencies", check_python_and_dependencies),
        ("Database ORM & RBAC Integrity", check_database_and_rbac),
        ("IaC Engine & Binary Discovery", check_iac_engine_and_binaries),
        ("Governance, Policy-as-Code & Risk Matrix", check_governance_and_risk),
        ("Kubernetes Control Plane & CRD Readiness", check_k8s_control_plane),
        ("Web Gateway & REST API Readiness", check_web_gateway_and_api),
    ]

    total_start = time.time()
    passed_count = 0
    total_count = len(checks)

    for i, (title, check_fn) in enumerate(checks, start=1):
        step_start = time.time()
        sys.stdout.write(f"[{i}/{total_count}] {title:<42} ... ")
        sys.stdout.flush()

        try:
            success, message = check_fn()
            duration = round(time.time() - step_start, 2)
            if success:
                passed_count += 1
                sys.stdout.write(f"{Colors.GREEN}{Colors.BOLD}[PASS]{Colors.RESET} ({duration:.2f}s)\n")
                sys.stdout.write(f"      * {message}\n")
            else:
                sys.stdout.write(f"{Colors.RED}{Colors.BOLD}[FAIL]{Colors.RESET} ({duration:.2f}s)\n")
                sys.stdout.write(f"      * Error: {message}\n")
        except Exception as e:
            duration = round(time.time() - step_start, 2)
            sys.stdout.write(f"{Colors.RED}{Colors.BOLD}[ERROR]{Colors.RESET} ({duration:.2f}s)\n")
            sys.stdout.write(f"      * Exception: {str(e)}\n")
            traceback.print_exc()

    total_duration = round(time.time() - total_start, 2)
    print(f"\n{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}")

    if passed_count == total_count:
        print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS] ALL SANITY CHECKS PASSED ({passed_count}/{total_count} checks OK in {total_duration:.2f}s){Colors.RESET}")
        print(f"{Colors.GREEN}System is sane, stable, and ready for production operations.{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}\n")
        return True
    else:
        failed_count = total_count - passed_count
        print(f"{Colors.RED}{Colors.BOLD}[FAILURE] SANITY CHECKS FAILED ({failed_count}/{total_count} checks failed in {total_duration:.2f}s){Colors.RESET}")
        print(f"{Colors.RED}Please review the failure details above before proceeding.{Colors.RESET}")
        print(f"{Colors.CYAN}{Colors.BOLD}======================================================================{Colors.RESET}\n")
        return False


if __name__ == "__main__":
    success = run_all_sanity_checks()
    sys.exit(0 if success else 1)

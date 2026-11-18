import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union

class IaCEngine(ABC):
    """Abstract Base Class for Infrastructure as Code CLI execution engines (Terraform, OpenTofu)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Friendly engine name (e.g. 'terraform', 'opentofu')."""
        pass

    @property
    @abstractmethod
    def binary(self) -> str:
        """CLI binary command name (e.g. 'terraform', 'tofu')."""
        pass

    def is_available(self) -> bool:
        """Check if the engine CLI binary is installed and executable on the PATH."""
        return shutil.which(self.binary) is not None

    def get_version(self) -> str:
        """Return the version string from `<binary> version`."""
        if not self.is_available():
            return "Not Installed"
        try:
            res = subprocess.run([self.binary, "version"], capture_output=True, text=True, timeout=5)
            first_line = res.stdout.strip().split("\n")[0] if res.stdout else "Unknown"
            return first_line
        except Exception as e:
            return f"Error: {e}"

    def _run_cmd(self, args: List[str], cwd: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Execute binary command in directory and return standardized result dictionary."""
        cmd = [self.binary] + args
        env = os.environ.copy()
        if "TF_PLUGIN_CACHE_DIR" not in env:
            shared_cache = os.path.join(os.path.expanduser("~"), ".terraform.d", "plugin-cache")
            try:
                os.makedirs(shared_cache, exist_ok=True)
                env["TF_PLUGIN_CACHE_DIR"] = shared_cache
            except Exception:
                pass
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            return {
                "success": res.returncode == 0,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "engine": self.name,
                "command": " ".join(cmd)
            }
        except FileNotFoundError:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Engine binary '{self.binary}' was not found on PATH.",
                "engine": self.name,
                "command": " ".join(cmd)
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s.",
                "engine": self.name,
                "command": " ".join(cmd)
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": str(e),
                "engine": self.name,
                "command": " ".join(cmd)
            }

    def fmt(self, filepath_or_dir: str) -> Dict[str, Any]:
        """Format an HCL file or directory."""
        if os.path.isfile(filepath_or_dir):
            cwd = os.path.dirname(filepath_or_dir)
            target = os.path.basename(filepath_or_dir)
        else:
            cwd = filepath_or_dir
            target = "."
        return self._run_cmd(["fmt", target], cwd=cwd, timeout=15)

    def is_initialized(self, cwd: str) -> bool:
        """Check if working directory has already been initialized with provider plugins."""
        tf_dir = os.path.join(cwd, ".terraform")
        providers_dir = os.path.join(tf_dir, "providers")
        return os.path.isdir(providers_dir) and bool(os.listdir(providers_dir))

    def init(self, cwd: str, backend: bool = False, upgrade: bool = False) -> Dict[str, Any]:
        """Initialize working directory with automatic self-healing for cross-platform provider caches."""
        args = ["init"]
        if not backend:
            args.append("-backend=false")
        if upgrade:
            args.append("-upgrade")
        res = self._run_cmd(args, cwd=cwd, timeout=300)

        # Self-healing: if provider plugins are missing or architecture mismatch occurred
        # (e.g. windows_amd64 vs linux_amd64 between host mounts and Docker container)
        err_lower = res.get("stderr", "").lower().replace("\\", "/")
        if not res["success"] and (
            "cached in .terraform/providers" in err_lower
            or "there is no package" in err_lower
            or "required plugins are not installed" in err_lower
            or "inconsistent with the packages selected in the dependency lock file" in err_lower
        ):
            providers_dir = os.path.join(cwd, ".terraform", "providers")
            if os.path.exists(providers_dir):
                import shutil
                try:
                    shutil.rmtree(providers_dir, ignore_errors=True)
                except Exception:
                    pass
            # Retry with -upgrade to fetch providers matching current runtime platform
            retry_args = ["init"]
            if not backend:
                retry_args.append("-backend=false")
            retry_args.append("-upgrade")
            res = self._run_cmd(retry_args, cwd=cwd, timeout=300)

        return res

    def validate(self, cwd: str) -> Dict[str, Any]:
        """Validate syntax and configuration consistency in directory."""
        if not self.is_initialized(cwd):
            init_res = self.init(cwd, backend=False)
            if not init_res["success"] and "already initialized" not in init_res.get("stderr", "").lower():
                return {
                    "success": False,
                    "exit_code": init_res["exit_code"],
                    "stdout": init_res["stdout"],
                    "stderr": f"{self.name.capitalize()} Init Failed:\n{init_res['stderr']}",
                    "engine": self.name
                }
        res = self._run_cmd(["validate"], cwd=cwd, timeout=60)
        err_lower = res.get("stderr", "").lower().replace("\\", "/")
        if not res["success"] and (
            "initialization required" in err_lower
            or "cached in .terraform/providers" in err_lower
            or "there is no package" in err_lower
        ):
            self.init(cwd, backend=False, upgrade=True)
            res = self._run_cmd(["validate"], cwd=cwd, timeout=60)
        return res

    def plan(self, cwd: str, is_destroy: bool = False, detailed_exitcode: bool = False) -> Dict[str, Any]:
        """Generate an execution plan."""
        if not self.is_initialized(cwd):
            init_res = self.init(cwd, backend=False)
            if not init_res["success"] and "already initialized" not in init_res.get("stderr", "").lower():
                return {
                    "success": False,
                    "exit_code": init_res["exit_code"],
                    "stdout": init_res["stdout"],
                    "stderr": f"{self.name.capitalize()} Init Failed:\n{init_res['stderr']}",
                    "engine": self.name
                }
        args = ["plan", "-no-color"]
        if is_destroy:
            args.append("-destroy")
        if detailed_exitcode:
            args.append("-detailed-exitcode")
        res = self._run_cmd(args, cwd=cwd, timeout=180)
        if not res["success"] and "initialization required" in res.get("stderr", "").lower():
            self.init(cwd, backend=False, upgrade=True)
            res = self._run_cmd(args, cwd=cwd, timeout=180)
        return res

    def apply(self, cwd: str, auto_approve: bool = True) -> Dict[str, Any]:
        """Apply the changes required to reach the desired state of the configuration."""
        if not self.is_initialized(cwd):
            init_res = self.init(cwd, backend=False)
            if not init_res["success"] and "already initialized" not in init_res.get("stderr", "").lower():
                return {
                    "success": False,
                    "exit_code": init_res["exit_code"],
                    "stdout": init_res["stdout"],
                    "stderr": f"{self.name.capitalize()} Init Failed:\n{init_res['stderr']}",
                    "engine": self.name
                }
        args = ["apply", "-no-color"]
        if auto_approve:
            args.append("-auto-approve")
        res = self._run_cmd(args, cwd=cwd, timeout=300)
        if not res["success"] and "initialization required" in res.get("stderr", "").lower():
            self.init(cwd, backend=False, upgrade=True)
            res = self._run_cmd(args, cwd=cwd, timeout=300)
        return res

    def destroy(self, cwd: str, auto_approve: bool = True) -> Dict[str, Any]:
        """Destroy all remote objects managed by a particular IaC configuration."""
        if not self.is_initialized(cwd):
            init_res = self.init(cwd, backend=False)
            if not init_res["success"] and "already initialized" not in init_res.get("stderr", "").lower():
                return {
                    "success": False,
                    "exit_code": init_res["exit_code"],
                    "stdout": init_res["stdout"],
                    "stderr": f"{self.name.capitalize()} Init Failed:\n{init_res['stderr']}",
                    "engine": self.name
                }
        args = ["destroy", "-no-color"]
        if auto_approve:
            args.append("-auto-approve")
        res = self._run_cmd(args, cwd=cwd, timeout=300)
        if not res["success"] and "initialization required" in res.get("stderr", "").lower():
            self.init(cwd, backend=False, upgrade=True)
            res = self._run_cmd(args, cwd=cwd, timeout=300)
        return res

    def show_state(self, cwd: str) -> Dict[str, Any]:
        """Show current state representation."""
        return self._run_cmd(["show", "-no-color"], cwd=cwd, timeout=60)

    @classmethod
    def generate_tenant_backend_hcl(
        cls,
        org_id: Union[str, int],
        project_slug: str,
        state_bucket: str = "terraform-ai-state",
        lock_table: str = "terraform-ai-locks",
        region: str = "us-east-1",
        encryption: bool = True
    ) -> str:
        """
        Generates a tenant-isolated S3 + DynamoDB state locking backend block
        preventing state collisions across organizations and projects.
        """
        clean_org = str(org_id).strip() or "default"
        clean_slug = str(project_slug).strip() or "workspace"
        
        return f"""# ── Tenant-Isolated Remote State Backend ({clean_org}/{clean_slug}) ──
terraform {{
  backend "s3" {{
    bucket         = "{state_bucket}"
    key            = "tenants/{clean_org}/{clean_slug}/terraform.tfstate"
    region         = "{region}"
    dynamodb_table = "{lock_table}"
    encrypt        = {str(encryption).lower()}
  }}
}}
"""

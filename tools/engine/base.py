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
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
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

    def init(self, cwd: str, backend: bool = False) -> Dict[str, Any]:
        """Initialize working directory."""
        args = ["init"]
        if not backend:
            args.append("-backend=false")
        return self._run_cmd(args, cwd=cwd, timeout=120)

    def validate(self, cwd: str) -> Dict[str, Any]:
        """Validate syntax and configuration consistency in directory."""
        # Ensure init has run first
        init_res = self.init(cwd, backend=False)
        if not init_res["success"] and "already initialized" not in init_res.get("stderr", "").lower():
            # If init fails, return init error
            return {
                "success": False,
                "exit_code": init_res["exit_code"],
                "stdout": init_res["stdout"],
                "stderr": f"{self.name.capitalize()} Init Failed:\n{init_res['stderr']}",
                "engine": self.name
            }
        return self._run_cmd(["validate"], cwd=cwd, timeout=60)

    def plan(self, cwd: str, is_destroy: bool = False, detailed_exitcode: bool = False) -> Dict[str, Any]:
        """Generate an execution plan."""
        self.init(cwd, backend=False)
        args = ["plan", "-no-color"]
        if is_destroy:
            args.append("-destroy")
        if detailed_exitcode:
            args.append("-detailed-exitcode")
        return self._run_cmd(args, cwd=cwd, timeout=180)

    def apply(self, cwd: str, auto_approve: bool = True) -> Dict[str, Any]:
        """Apply the changes required to reach the desired state of the configuration."""
        args = ["apply", "-no-color"]
        if auto_approve:
            args.append("-auto-approve")
        return self._run_cmd(args, cwd=cwd, timeout=300)

    def destroy(self, cwd: str, auto_approve: bool = True) -> Dict[str, Any]:
        """Destroy all remote objects managed by a particular IaC configuration."""
        args = ["destroy", "-no-color"]
        if auto_approve:
            args.append("-auto-approve")
        return self._run_cmd(args, cwd=cwd, timeout=300)

    def show_state(self, cwd: str) -> Dict[str, Any]:
        """Show current state representation."""
        return self._run_cmd(["show", "-no-color"], cwd=cwd, timeout=60)

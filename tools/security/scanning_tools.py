import subprocess
import json
import os
import platform
import shutil

class SecurityAuditor:
    def __init__(self, tfsec_path=None):
        # Auto-detect tfsec binary based on platform
        if tfsec_path:
            self.tfsec_path = os.path.abspath(tfsec_path)
        elif platform.system() == "Windows":
            self.tfsec_path = os.path.abspath("tfsec.exe")
        else:
            # On Linux/Mac, check if tfsec is in PATH or local directory
            self.tfsec_path = shutil.which("tfsec") or os.path.abspath("tfsec")
        
        self.checkov_image = "bridgecrew/checkov:latest"
        # Check if we're running inside Docker (checkov installed natively)
        self._use_native_checkov = shutil.which("checkov") is not None

    def _convert_path_for_docker(self, path):
        r"""
        Converts a Windows absolute path to a format friendly for Docker volumes.
        On Linux/Mac, returns the path as-is.
        """
        abs_path = os.path.abspath(path)
        if platform.system() == "Windows":
            return abs_path.replace("\\", "/")
        return abs_path

    def run_tfsec_scan(self, directory_path):
        """
        Runs tfsec (Local Binary) - FAST.
        """
        if not os.path.exists(self.tfsec_path) and not shutil.which("tfsec"):
            return []  # tfsec not available, skip gracefully

        try:
            result = subprocess.run(
                [self.tfsec_path, directory_path, "-f", "json", "--soft-fail"],
                capture_output=True,
                text=True
            )
            if not result.stdout:
                return []

            data = json.loads(result.stdout)
            findings = []
            if "results" in data and data["results"]:
                for res in data["results"]:
                    if res.get("status") != "passed":
                        findings.append({
                            "engine": "tfsec",
                            "rule_id": res.get("rule_id"),
                            "severity": res.get("severity", "medium").upper(),
                            "description": res.get("description"),
                            "resolution": res.get("resolution"),
                            "impact": res.get("impact")
                        })
            return findings
        except Exception:
            return []

    def run_checkov_scan(self, directory_path):
        """
        Runs Checkov — natively if available, otherwise via Docker.
        """
        if self._use_native_checkov:
            return self._run_checkov_native(directory_path)
        return self._run_checkov_docker(directory_path)

    def _run_checkov_native(self, directory_path):
        """Runs Checkov directly (used when inside Docker container)."""
        abs_path = os.path.abspath(directory_path)
        command = [
            "checkov", "-d", abs_path,
            "--output", "json",
            "--soft-fail"
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            return self._parse_checkov_output(result.stdout)
        except Exception:
            return []

    def _run_checkov_docker(self, directory_path):
        """Runs Checkov via Docker container (used on host machines)."""
        docker_path = self._convert_path_for_docker(directory_path)
        command = [
            "docker", "run", "--rm",
            "-v", f"{docker_path}:/tf",
            self.checkov_image,
            "-d", "/tf",
            "--output", "json",
            "--soft-fail"
        ]
        
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            return self._parse_checkov_output(result.stdout)
        except Exception:
            return []

    def _parse_checkov_output(self, stdout):
        """Parses Checkov JSON output into a unified findings list."""
        if not stdout:
            return []
        try:
            data = json.loads(stdout)
            if not isinstance(data, list):
                data = [data]

            findings = []
            for report in data:
                failed_checks = report.get("results", {}).get("failed_checks", [])
                for check in failed_checks:
                    findings.append({
                        "engine": "checkov",
                        "rule_id": check.get("check_id"),
                        "severity": (check.get("severity") or "medium").upper(),
                        "description": check.get("check_name"),
                        "resolution": check.get("guideline") or "Follow standard best practices.",
                        "impact": "Security vulnerability detected in configuration"
                    })
            return findings
        except (json.JSONDecodeError, KeyError):
            return []

    def run_comprehensive_scan(self, directory_path, mode="checkov"):
        """
        Orchestrates security scans. Default is deep checkov.
        Returns a unified result object.
        """
        print(f"  [Security] Initiating {mode.upper()} scan...")
        
        if mode == "checkov":
            findings = self.run_checkov_scan(directory_path)
        else:
            findings = self.run_tfsec_scan(directory_path)

        return {
            "summary": {
                "total_failed": len(findings),
                "passed": len(findings) == 0,
                "engine": mode
            },
            "findings": findings
        }

    def format_report(self, audit_result):
        summary = audit_result["summary"]
        engine = summary["engine"].upper()
        
        if summary["passed"]:
            return f"Security Health Check ({engine}): PASSED (All clear!)"

        report = f"Security Health Check ({engine}): FAILED (Found {summary['total_failed']} issues)\n"
        report += "--------------------------------------------------\n"
        
        for i, finding in enumerate(audit_result["findings"], 1):
            severity = finding["severity"]
            report += f"{i}. [{severity}] {finding['rule_id']}: {finding['description']}\n"
            report += f"   Resolution: {finding['resolution']}\n"
            if finding.get("impact"):
                report += f"   Impact: {finding['impact']}\n"
            report += "\n"
            
        return report


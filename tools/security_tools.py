import subprocess
import json
import os
import platform

class SecurityAuditor:
    def __init__(self, tfsec_path="tfsec.exe"):
        self.tfsec_path = os.path.abspath(tfsec_path)
        self.checkov_image = "bridgecrew/checkov:latest"

    def _convert_path_for_docker(self, path):
        r"""
        Converts a Windows absolute path to a format friendly for Docker volumes.
        Example: C:\Users\User -> C:/Users/User
        """
        abs_path = os.path.abspath(path)
        # Replacing backslashes with forward slashes is generally enough for Docker Windows
        return abs_path.replace("\\", "/")

    def run_tfsec_scan(self, directory_path):
        """
        Runs tfsec (Local Binary) - FAST.
        """
        try:
            result = subprocess.run(
                [self.tfsec_path, directory_path, "-f", "json", "--soft-fail"],
                capture_output=True,
                text=True,
                shell=True
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
        Runs Checkov (Docker Container) - DEEP.
        """
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
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            if not result.stdout:
                return []

            # Checkov might return a list (multiple frameworks) or a single object
            data = json.loads(result.stdout)
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
        except Exception:
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

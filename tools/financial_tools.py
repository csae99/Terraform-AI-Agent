import subprocess
import json
import os
import platform
import shutil
from crewai.tools import tool

class CostEstimator:
    def __init__(self, binary_path=None):
        # Auto-detect infracost binary
        if binary_path:
            self.binary_path = os.path.abspath(binary_path)
        elif platform.system() == "Windows":
            self.binary_path = os.path.abspath("infracost.exe")
        else:
            self.binary_path = shutil.which("infracost") or os.path.abspath("infracost")
        
        # Check if infracost is installed natively (inside Docker or local install)
        self._use_native = shutil.which("infracost") is not None

    @tool
    def get_monthly_cost(directory_path: str) -> str:
        """
        Runs infracost breakdown on the target directory and returns a cost summary.
        Args:
            directory_path (str): Path to the terraform workspace.
        """
        estimator = CostEstimator()
        result = estimator._execute_infracost(directory_path)
        return estimator.format_report(result)

    @tool
    def generate_financial_report(project_slug: str, budget: float = 100.0) -> str:
        """
        Generates a detailed FINANCIAL_REPORT.md file with budget comparison and optimizations.
        Args:
            project_slug (str): The slug identifying the workspace.
            budget (float): The monthly budget limit to compare against.
        """
        directory_path = os.path.join("output", project_slug)
        estimator = CostEstimator()
        result = estimator._execute_infracost(directory_path)
        
        if "error" in result:
            return f"Failed to generate report: {result['details']}"
            
        report_content = estimator._build_markdown_report(result, budget)
        report_path = os.path.join(directory_path, "FINANCIAL_REPORT.md")
        
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            return f"Financial report generated successfully at {report_path}"
        except Exception as e:
            return f"Error writing report: {str(e)}"

    def _execute_infracost(self, project_path):
        """Runs infracost to get the cost breakdown in JSON format.
        Uses native binary if available, otherwise falls back to Docker."""
        # Check if project_path exists, if not, try prepending 'output/'
        if not os.path.exists(project_path):
            alt_path = os.path.join("output", project_path)
            if os.path.exists(alt_path):
                project_path = alt_path
            else:
                return {"error": "PATH_NOT_FOUND", "details": f"Directory {project_path} (or output/{project_path}) does not exist."}

        api_key = os.getenv("INFRACOST_API_KEY")
        if not api_key or "your_" in api_key:
            return {"error": "API_KEY_MISSING", "details": "INFRACOST_API_KEY is not set in .env"}

        abs_project_path = os.path.abspath(project_path)

        try:
            if self._use_native:
                # Native mode: infracost installed directly (e.g., inside Docker)
                cmd = [
                    "infracost", "breakdown",
                    "--path", abs_project_path,
                    "--format", "json"
                ]
                env = os.environ.copy()
                env["INFRACOST_API_KEY"] = api_key
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            else:
                # Docker mode: run infracost via Docker container
                current_dir = os.getcwd()
                relative_path = os.path.relpath(abs_project_path, current_dir)
                # Normalize path separators for Docker
                if platform.system() == "Windows":
                    relative_path = relative_path.replace("\\", "/")
                
                cmd = [
                    "docker", "run", "--rm",
                    "-v", f"{current_dir}:/code",
                    "-e", f"INFRACOST_API_KEY={api_key}",
                    "infracost/infracost:latest",
                    "breakdown",
                    "--path", f"/code/{relative_path}",
                    "--format", "json"
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return {"error": "INFRACOST_FAILURE", "details": result.stderr}

            data = json.loads(result.stdout)
            return {
                "total_monthly_cost": data.get("totalMonthlyCost", "0.00"),
                "currency": data.get("currency", "USD"),
                "resources": data.get("projects", [{}])[0].get("breakdown", {}).get("resources", []),
                "all_data": data
            }
        except Exception as e:
            return {"error": "EXECUTION_ERROR", "details": str(e)}

    def _build_markdown_report(self, result, budget_limit=100.0):
        cost = float(result.get("total_monthly_cost", 0))
        currency = result.get("currency", "USD")
        resources = result.get("resources", [])
        
        # Calculate variance
        variance = cost - budget_limit
        is_over = variance > 0
        
        report = f"# 📊 Financial Intelligence & Optimization Report\n\n"
        
        report += f"## 💰 Budget Compliance Status\n"
        if is_over:
            report += f"### ⚠️ **STATUS: OVER BUDGET**\n"
            report += f"- **Allocated Budget:** `${budget_limit:.2f}`\n"
            report += f"- **Projected Cost:** `${cost:.2f}`\n"
            report += f"- **Excess Amount:** 🔴 `${variance:.2f}` {currency} over limit.\n\n"
        else:
            report += f"### ✅ **STATUS: WITHIN BUDGET**\n"
            report += f"- **Allocated Budget:** `${budget_limit:.2f}`\n"
            report += f"- **Projected Cost:** `${cost:.2f}`\n"
            report += f"- **Savings/Buffer:** 🟢 `${abs(variance):.2f}` {currency} remaining.\n\n"
        
        report += "### 🏗️ Resource-Level Breakdown\n"
        report += "| Resource Category | Monthly Cost | Currency | Impact |\n"
        report += "| :--- | :--- | :--- | :--- |\n"
        
        if not resources:
            report += "| No billable resources | 0.00 | USD | ✅ NONE |\n"
        else:
            for res in resources:
                r_cost = float(res.get("monthlyCost", 0))
                impact = "🔥 HIGH" if r_cost > (budget_limit * 0.2) else "⚖️ MED" if r_cost > 5 else "💧 LOW"
                report += f"| {res.get('name')} | {r_cost:.2f} | {currency} | {impact} |\n"
        
        report += "\n## 💡 Optimization Recommendations\n"
        
        has_aws = any("aws_" in str(res.get('name', '')).lower() for res in resources)
        has_compute = any("instance" in str(res.get('name', '')).lower() or "lambda" in str(res.get('name', '')).lower() for res in resources)
        
        if not resources:
            report += "1. **Local Execution**: No billable cloud resources detected. Cost is $0.\n"
            report += "2. **Architecture Efficiency**: Current local-first approach is 100% cost-optimized.\n"
        elif is_over:
            if has_aws and has_compute:
                report += "1. **Right-Sizing**: Consider switching to smaller instance types for the highest impact resources.\n"
                report += "2. **Spot Instances**: If this is a dev/test environment, evaluate using Spot instances for up to 90% savings.\n"
            else:
                report += "1. **Resource Consolidation**: Review if billable resources can be shared or removed.\n"
            report += "3. **Cleanup**: Ensure all resources are tagged for automated destruction after their lifecycle.\n"
        else:
            report += "1. **Maintain Current State**: All resources are within efficient spending boundaries.\n"
            if has_aws and has_compute:
                report += "2. **Reserved Instances**: If this load is permanent, consider 1-year reservations for further 30% savings.\n"
            elif not has_aws:
                report += "2. **Zero-Waste**: Architecture relies on low-cost or local providers, minimizing financial risk.\n"

        
        report += "\n---\n*Report generated by **Terraform AI Agent (FinOps Module v2.1)** • Verified via Infracost Cloud API*"
        return report

    def format_report(self, cost_result):
        if "error" in cost_result:
            return f"Cost Estimation Error: {cost_result['details']}"

        cost = cost_result["total_monthly_cost"]
        currency = cost_result["currency"]
        
        return f"✅ PROJECTED MONTHLY COST: {cost} {currency}\nDetailed audit available in FINANCIAL_REPORT.md."

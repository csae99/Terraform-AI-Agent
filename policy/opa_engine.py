import os
import re
import json
import subprocess
from typing import Dict, List, Any, Optional

class OPAEngine:
    """
    Open Policy Agent (OPA) / Rego Policy-as-Code Engine.
    Evaluates Terraform/OpenTofu infrastructure against enterprise compliance packs
    (SOC2, HIPAA, PCI-DSS, CIS Benchmarks) with pure Python fallback.
    """

    COMPLIANCE_PACKS_DIR = os.path.join(os.path.dirname(__file__), "compliance")

    @classmethod
    def evaluate_compliance(cls, hcl_code_or_path: str, pack: str = "soc2") -> Dict[str, Any]:
        """
        Evaluates HCL code or directory against the selected compliance pack.
        """
        pack_file = os.path.join(cls.COMPLIANCE_PACKS_DIR, f"{pack}.rego")
        if not os.path.exists(pack_file):
            return {
                "allow": False,
                "pack": pack,
                "error": f"Compliance pack '{pack}' not found in {cls.COMPLIANCE_PACKS_DIR}",
                "violations": [f"Unknown compliance pack: {pack}"],
                "compliance_score_percent": 0.0
            }

        # 1. Parse HCL into structured resource AST
        input_ast = cls._parse_hcl_to_ast(hcl_code_or_path)

        # 2. Try native OPA CLI first if available
        native_result = cls._run_opa_cli(pack_file, input_ast)
        if native_result is not None:
            return native_result

        # 3. Fallback: Pure-Python AST rule evaluator for standard packs
        return cls._evaluate_python_ast(input_ast, pack)

    @classmethod
    def _parse_hcl_to_ast(cls, hcl_code_or_path: str) -> Dict[str, Any]:
        """
        Parses HCL string or files in a directory into a normalized input JSON dictionary.
        """
        raw_text = ""
        if os.path.isdir(hcl_code_or_path):
            for root, _, files in os.walk(hcl_code_or_path):
                for f in files:
                    if f.endswith((".tf", ".tofu")):
                        with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fp:
                            raw_text += fp.read() + "\n"
        elif os.path.isfile(hcl_code_or_path):
            with open(hcl_code_or_path, "r", encoding="utf-8", errors="ignore") as fp:
                raw_text = fp.read()
        else:
            raw_text = str(hcl_code_or_path)

        resources = []
        
        # Regex extraction of resource blocks: resource "type" "name" { ... }
        pattern = r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        for match in re.finditer(pattern, raw_text, re.DOTALL):
            r_type, r_name, body = match.groups()
            
            # Simple attribute parser
            values = {}
            for line in body.split("\n"):
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v.lower() == "true":
                        values[k] = True
                    elif v.lower() == "false":
                        values[k] = False
                    elif v.isdigit():
                        values[k] = int(v)
                    else:
                        values[k] = v

            # Check special flags
            if "block_public_acls" in body and "true" in body:
                values["block_public_acls"] = True
                values["block_public_policy"] = True
            if "storage_encrypted" in body and "true" in body:
                values["storage_encrypted"] = True
            if "encrypted" in body and "true" in body:
                values["encrypted"] = True
            if "publicly_accessible" in body and "false" in body:
                values["publicly_accessible"] = False
            elif "publicly_accessible" in body and "true" in body:
                values["publicly_accessible"] = True

            resources.append({
                "type": r_type,
                "name": r_name,
                "values": values,
                "raw_body": body
            })

        return {"resources": resources, "raw_hcl": raw_text}

    @classmethod
    def _run_opa_cli(cls, rego_path: str, input_ast: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Executes OPA binary if available on system PATH."""
        try:
            input_json = json.dumps({"input": input_ast})
            res = subprocess.run(
                ["opa", "eval", "-d", rego_path, "-I", "data.compliance"],
                input=input_json,
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                data = json.loads(res.stdout)
                # Parse OPA evaluation results
                return data
        except Exception:
            pass
        return None

    @classmethod
    def _evaluate_python_ast(cls, ast: Dict[str, Any], pack: str) -> Dict[str, Any]:
        """
        Pure Python evaluator implementing the core rules defined in the compliance packs.
        """
        resources = ast.get("resources", [])
        violations = []
        rules_checked = 0

        if pack == "soc2":
            # 1. S3 Public Access Block
            s3_buckets = [r for r in resources if r["type"] == "aws_s3_bucket"]
            pabs = [r for r in resources if r["type"] == "aws_s3_bucket_public_access_block"]
            for b in s3_buckets:
                rules_checked += 1
                has_pab = any(b["name"] in p.get("raw_body", "") for p in pabs)
                if not has_pab and not b["values"].get("block_public_acls"):
                    violations.append(f"SOC2 Violation: S3 bucket '{b['name']}' must have aws_s3_bucket_public_access_block configured.")

            # 2. S3 Server-side encryption
            sses = [r for r in resources if "encryption" in r["type"]]
            for b in s3_buckets:
                rules_checked += 1
                has_sse = any(b["name"] in s.get("raw_body", "") for s in sses) or b["values"].get("encrypted")
                if not has_sse and "sse" not in ast.get("raw_hcl", "").lower():
                    violations.append(f"SOC2 Violation: S3 bucket '{b['name']}' must have server-side encryption configured.")

            # 3. RDS storage encryption
            db_instances = [r for r in resources if r["type"] == "aws_db_instance"]
            for db in db_instances:
                rules_checked += 1
                if not db["values"].get("storage_encrypted", False):
                    violations.append(f"SOC2 Violation: RDS database '{db['name']}' must have storage_encrypted=true.")

            # 4. Security group 0.0.0.0/0 on sensitive ports
            sgs = [r for r in resources if "security_group" in r["type"]]
            for sg in sgs:
                rules_checked += 1
                raw = sg.get("raw_body", "")
                if "0.0.0.0/0" in raw and any(p in raw for p in ["22", "3389", "5432", "3306"]):
                    violations.append(f"SOC2 Violation: Security group '{sg['name']}' allows open 0.0.0.0/0 access to sensitive ports.")

        elif pack == "hipaa":
            db_instances = [r for r in resources if r["type"] == "aws_db_instance"]
            for db in db_instances:
                rules_checked += 2
                if db["values"].get("publicly_accessible") is True:
                    violations.append(f"HIPAA Violation: RDS database '{db['name']}' must not be publicly accessible.")
                backup_period = db["values"].get("backup_retention_period", 0)
                if isinstance(backup_period, int) and backup_period < 7 and "backup_retention_period" in db["values"]:
                    violations.append(f"HIPAA Violation: RDS database '{db['name']}' backup_retention_period must be >= 7 days.")

        elif pack == "pci_dss":
            for r in resources:
                if "ebs_volume" in r["type"]:
                    rules_checked += 1
                    if not r["values"].get("encrypted", False):
                        violations.append(f"PCI-DSS Violation: EBS volume '{r['name']}' must be encrypted.")
                if "security_group" in r["type"] and "0.0.0.0/0" in r.get("raw_body", ""):
                    rules_checked += 1
                    if "443" not in r.get("raw_body", "") and "80" in r.get("raw_body", ""):
                        violations.append(f"PCI-DSS Violation: Security group '{r['name']}' allows unencrypted HTTP 0.0.0.0/0 ingress.")

        elif pack == "cis_benchmarks":
            s3_buckets = [r for r in resources if r["type"] == "aws_s3_bucket"]
            for b in s3_buckets:
                rules_checked += 1
                if "versioning" not in ast.get("raw_hcl", "").lower():
                    violations.append(f"CIS Benchmark Violation: S3 bucket '{b['name']}' must have versioning enabled.")

        if rules_checked == 0:
            rules_checked = 1  # Base check
            score = 100.0
        else:
            passed = max(0, rules_checked - len(violations))
            score = round((passed / rules_checked) * 100.0, 1)

        return {
            "allow": len(violations) == 0,
            "pack": pack.upper(),
            "compliance_score_percent": score,
            "violations_count": len(violations),
            "violations": violations,
            "rules_checked": rules_checked
        }

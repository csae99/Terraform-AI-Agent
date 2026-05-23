import os
import subprocess
import json

abs_path = os.path.abspath("output/productionvalid-aws-eks")
docker_path = abs_path.replace("\\", "/")

cmd = [
    "docker", "run", "--rm",
    "-v", f"{docker_path}:/tf",
    "bridgecrew/checkov:latest",
    "-d", "/tf",
    "--output", "json",
    "--soft-fail"
]

print("Running command:", " ".join(cmd))
res = subprocess.run(cmd, capture_output=True, text=True)
print("Return code:", res.returncode)
print("Stdout length:", len(res.stdout))
print("Stderr:", res.stderr[:500])

if res.stdout:
    try:
        data = json.loads(res.stdout)
        print("Findings count:", len(data.get("results", {}).get("failed_checks", [])))
    except Exception as e:
        print("JSON parse error:", e)
        print("Stdout preview:", res.stdout[:200])

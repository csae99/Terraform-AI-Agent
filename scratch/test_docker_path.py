import os
import subprocess
import json

current_dir = os.getcwd()
relative_path = "output/productionvalid-aws-eks"
if os.name == "nt":
    relative_path = relative_path.replace("\\", "/")

print("Using backslashes:")
cmd1 = [
    "docker", "run", "--rm",
    "-v", f"{current_dir}:/code",
    "alpine", "ls", "-l", f"/code/{relative_path}"
]
print(" ".join(cmd1))
res1 = subprocess.run(cmd1, capture_output=True, text=True)
print("Return code:", res1.returncode)
print("Stdout:", res1.stdout)
print("Stderr:", res1.stderr)

print("\nUsing forward slashes:")
current_dir_fwd = current_dir.replace("\\", "/")
cmd2 = [
    "docker", "run", "--rm",
    "-v", f"{current_dir_fwd}:/code",
    "alpine", "ls", "-l", f"/code/{relative_path}"
]
print(" ".join(cmd2))
res2 = subprocess.run(cmd2, capture_output=True, text=True)
print("Return code:", res2.returncode)
print("Stdout:", res2.stdout)
print("Stderr:", res2.stderr)

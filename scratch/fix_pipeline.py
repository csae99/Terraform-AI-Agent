import re
import os

with open("orchestrator/pipeline.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# The duplicate block starts at line 261 (0-indexed 260) and goes up to line 310 (0-indexed 309).
# Let's verify by checking the lines around 261.
for idx, line in enumerate(lines):
    if "findings = audit_results.get(\"findings\", [])" in line:
        print(f"Found 'findings =' at line {idx + 1}")

# We have it twice! Once around 211 and once around 261.
# The `else:` for `if retry.current_round < retry.max_rounds:` is at line 311.
# Let's just fix the loop so it's clean and syntactically correct.

import os

file_path = "orchestrator/pipeline.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's find the start of the try block which shouldn't be there because my replace failed.
# The user wants me to fix the "stuck in generating state" issue.
# This means I need to safely catch exceptions inside run_full_pipeline, mark state as 'failed', and then raise.

# Let's completely rewrite the run_full_pipeline function from lines 70 to the end.

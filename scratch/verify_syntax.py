import sys
import os

# Add parent directory to path to import tools
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_syntax():
    files = [
        "orchestrator/pipeline.py",
        "app/main.py",
        "app/dashboard.py"
    ]
    
    all_ok = True
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                source = file.read()
            compile(source, f, "exec")
            print(f"✅ Syntax check passed for: {f}")
        except Exception as e:
            print(f"❌ Syntax check failed for: {f}. Error: {e}")
            all_ok = False
            
    if not all_ok:
        sys.exit(1)
    else:
        print("🎉 All modified Python files compiled successfully!")

if __name__ == "__main__":
    check_syntax()

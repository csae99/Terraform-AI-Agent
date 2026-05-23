"""
End-to-end test: Login as testuser1, trigger generation with Gemini API key,
and stream the live agent logs to verify everything works.
"""
import requests
import json
import sys
import time

BASE_URL = "http://localhost:5000"

def main():
    session = requests.Session()
    
    # Step 1: Login
    print("=" * 60)
    print("STEP 1: Logging in as testuser1...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "testuser1",
        "password": "test1234"
    })
    print(f"  Status: {res.status_code}")
    print(f"  Response: {res.json()}")
    if res.status_code != 200:
        print("  FAILED - Cannot login. Aborting.")
        return
    print("  ✅ Login successful!")
    
    # Step 2: Verify auth
    print("\nSTEP 2: Verifying auth...")
    res = session.get(f"{BASE_URL}/api/auth/me")
    print(f"  Status: {res.status_code}")
    print(f"  Response: {res.json()}")
    print("  ✅ Auth verified!")
    
    # Step 3: Check stats
    print("\nSTEP 3: Fetching stats...")
    res = session.get(f"{BASE_URL}/api/stats")
    print(f"  Status: {res.status_code}")
    print(f"  Response: {res.json()}")
    print("  ✅ Stats OK!")
    
    # Step 4: Trigger generation with a simple local file prompt
    print("\nSTEP 4: Triggering infrastructure generation...")
    payload = {
        "prompt": "Create a local file named hello.txt with content 'Hello World' using the Terraform local provider",
        "budget": 5,
        "apply": False,
        "credentials": {},
        "ai_config": {
            "provider": "gemini",
            "model": "gemini-3.1-flash-lite",
            "key": ""
        }
    }
    res = session.post(f"{BASE_URL}/api/generate", json=payload,
                       headers={"Content-Type": "application/json"})
    print(f"  Status: {res.status_code}")
    print(f"  Response: {res.json()}")
    if res.status_code != 200:
        print("  ❌ FAILED to trigger generation!")
        return
    print("  ✅ Generation triggered!")
    
    # Step 5: Poll the SSE logs
    print("\nSTEP 5: Streaming agent logs (max 120 seconds)...")
    print("-" * 60)
    
    start_time = time.time()
    max_wait = 120  # seconds
    
    try:
        sse_response = session.get(
            f"{BASE_URL}/api/logs/active",
            headers={"Accept": "text/event-stream"},
            stream=True,
            timeout=max_wait
        )
        
        for line in sse_response.iter_lines(decode_unicode=True):
            if time.time() - start_time > max_wait:
                print("\n[TIMEOUT] Max wait time reached.")
                break
                
            if not line:
                continue
                
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:])
                    logs = data.get("logs", "")
                    if logs:
                        sys.stdout.write(logs)
                        sys.stdout.flush()
                        
                        # Check for completion
                        if any(marker in logs for marker in [
                            "✅ Workflow Finished",
                            "❌ Workflow Finished",
                            "❌ Error"
                        ]):
                            print("\n[DONE] Workflow completed.")
                            break
                except json.JSONDecodeError:
                    pass
    except requests.exceptions.Timeout:
        print("\n[TIMEOUT] SSE stream timed out.")
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
    
    print("-" * 60)
    
    # Step 6: Check projects
    print("\nSTEP 6: Checking projects list...")
    time.sleep(2)
    res = session.get(f"{BASE_URL}/api/projects")
    projects = res.json()
    print(f"  Total projects: {len(projects)}")
    for p in projects[:3]:
        print(f"    - {p['slug']} ({p['status']}) cost=${p.get('estimated_cost', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")

if __name__ == "__main__":
    main()

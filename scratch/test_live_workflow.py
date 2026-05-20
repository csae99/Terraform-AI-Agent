import requests
import json
import time
import random
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_test():
    session = requests.Session()
    
    # Generate unique credentials
    username = f"testuser_{random.randint(1000, 9999)}"
    password = "password123"
    
    print(f"Registering user: {username}...")
    res = session.post(f"{BASE_URL}/api/auth/register", json={
        "username": username,
        "password": password,
        "email": f"{username}@example.com"
    })
    print("Registration Response:", res.status_code, res.json())
    assert res.status_code == 200, "Registration failed"
    
    print("Logging in...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": username,
        "password": password
    })
    print("Login Response:", res.status_code, res.json())
    assert res.status_code == 200, "Login failed"
    
    # Define generation payload with user's Gemini API key
    payload = {
        "prompt": "Create a local file resource named greeting.txt with content 'Hello from Antigravity Agent!' using local provider",
        "budget": 5,
        "apply": True,
        "ai_config": {
            "model": "gemini-2.0-flash",
            "provider": "gemini",
            "key": "AIzaSyC283dI15JyTciEC6Ihljkw2WllRB_bhQM"
        }
    }
    
    print("Submitting generation request...")
    res = session.post(f"{BASE_URL}/api/generate", json=payload)
    print("Generation Submit Response:", res.status_code, res.json())
    assert res.status_code == 200, "Generation trigger failed"
    
    print("\nStreaming agent logs (SSE):")
    # Stream logs via SSE
    # We must pass session cookies since FastAPI requires authentication
    headers = {"Accept": "text/event-stream"}
    # SSE request using requests.get with stream=True
    sse_response = session.get(f"{BASE_URL}/api/logs/active", headers=headers, stream=True)
    
    for line in sse_response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data:"):
                try:
                    data = json.loads(decoded_line[5:])
                    logs = data.get("logs", "")
                    if logs:
                        sys.stdout.write(logs)
                        sys.stdout.flush()
                except Exception as e:
                    pass
            
            # Stop streaming when workflow ends
            if b"Workflow Finished" in line or b"Error:" in line:
                print("\nWorkflow finished or error encountered.")
                break
                
    time.sleep(2)
    print("\nVerifying projects list...")
    res = session.get(f"{BASE_URL}/api/projects")
    print("Projects Response:", res.status_code, res.json())

if __name__ == "__main__":
    run_test()

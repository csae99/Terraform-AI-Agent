import requests
import json
import sys
import time

BASE_URL = "http://127.0.0.1:5000"

def run():
    session = requests.Session()
    username = "testuser1"
    password = "test1234"
    
    print(f"Attempting to log in as {username}...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": username,
        "password": password
    })
    
    if res.status_code != 200:
        print("Login failed, attempting registration...")
        res = session.post(f"{BASE_URL}/api/auth/register", json={
            "username": username,
            "password": password,
            "email": "testuser1@example.com"
        })
        print("Registration response:", res.status_code, res.json())
        
        # Try logging in again
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": password
        })
        print("Second Login response:", res.status_code, res.json())
        assert res.status_code == 200, "Could not authenticate"
    else:
        print("Logged in successfully!")

    prompt = (
        "Create a production-valid Terraform configuration for AWS EKS with:\n\n"
        "* EKS Auto Mode NOT enabled\n"
        "* public EKS API endpoint enabled\n"
        "* managed node group using m5.4xlarge\n"
        "* node group max size = 5\n"
        "* minimum 2 public subnets across different AZs\n"
        "* VPC, IGW, route tables, subnet associations\n"
        "* required IAM roles AND policy attachments\n"
        "* security groups\n"
        "* provider.tf and versions.tf\n"
        "* outputs.tf\n"
        "* tags required for Kubernetes LoadBalancer support\n"
        "* Terraform AWS provider v5+\n"
        "* code must pass terraform validate\n"
        "* code should be deployable without modification"
    )
    
    payload = {
        "prompt": prompt,
        "budget": 100.0,
        "apply": False,
        "ai_config": {
            "model": "gemini-3.1-flash-lite",
            "provider": "gemini",
            "key": "AIzaSyDvwxYTOcgr546EeY4PE481nU6fy8pX0Tk"
        }
    }
    
    print("Submitting infrastructure generation request...")
    res = session.post(f"{BASE_URL}/api/generate", json=payload)
    print("Generate Response status:", res.status_code)
    print("Generate Response body:", res.json())
    assert res.status_code == 200, "Generation submission failed"
    
    print("\nStreaming active logs:")
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
            if b"Workflow Finished" in line or b"Error:" in line or b"error" in line.lower():
                print("\nWorkflow finished or error encountered in line stream.")
                break

if __name__ == "__main__":
    run()

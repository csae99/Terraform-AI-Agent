import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_api():
    session = requests.Session()
    username = "testuser1"
    password = "test1234"
    
    print(f"Logging in as {username}...")
    res = session.post(f"{BASE_URL}/api/auth/login", json={
        "username": username,
        "password": password
    })
    
    if res.status_code != 200:
        print("Login failed, trying register...")
        session.post(f"{BASE_URL}/api/auth/register", json={
            "username": username,
            "password": password
        })
        res = session.post(f"{BASE_URL}/api/auth/login", json={
            "username": username,
            "password": password
        })
        
    print("Login status:", res.status_code)
    assert res.status_code == 200
    
    # Send a tiny prompt to verify slug behavior
    payload = {
        "prompt": "Create VPC only",
        "budget": 10.0,
        "apply": False,
        "new_project": True,
        "ai_config": {
            "model": "gemini-3.1-flash-lite",
            "provider": "gemini",
            "key": "AIzaSyDvwxYTOcgr546EeY4PE481nU6fy8pX0Tk"
        }
    }
    
    print("Sending API generate request with new_project=True...")
    res = session.post(f"{BASE_URL}/api/generate", json=payload)
    print("Generate Response:", res.status_code, res.json())

if __name__ == "__main__":
    test_api()

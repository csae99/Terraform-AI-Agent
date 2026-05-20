import requests
import json

session = requests.Session()
# Register and login to be authenticated
username = "admin"
password = "adminpassword"
session.post("http://127.0.0.1:5000/api/auth/register", json={"username": username, "password": password})
session.post("http://127.0.0.1:5000/api/auth/login", json={"username": username, "password": password})

res = session.get("http://127.0.0.1:5000/api/logs/active", stream=True)
print("Status Code:", res.status_code)
for line in res.iter_lines():
    if line:
        print(line.decode('utf-8'))

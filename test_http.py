import requests
import json
import time

try:
    print("Sending Generate request...")
    response = requests.post(
        "http://localhost:8000/generate", 
        json={"mood": "happy", "creativity": 0.8, "tempo": 120, "duration": 30},
        timeout=60
    )
    print("Status:", response.status_code)
    print("Body:", response.text)
except Exception as e:
    print("Request failed:", e)

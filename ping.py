import requests

try:
    response = requests.post(
        "https://neurocomposer-api.onrender.com/generate", 
        json={"mood": "happy", "creativity": 0.8, "tempo": 120},
        timeout=30
    )
    print("Status:", response.status_code)
    print("Body:", response.text)
except Exception as e:
    print("Request failed:", e)

import requests
response = requests.post("https://neurocomposer-api.onrender.com/generate", json={"mood": "happy", "creativity": 0.8, "tempo": 120})
print(response.status_code)
print(response.text)

import requests
import json
import time

url = "http://localhost:5002/generate"
prompt = "The capital of France is"

payload = {
    "prompt": prompt,
    "max_tokens": 10,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40
}

print(f"Sending request to {url}...")
print(f"Prompt: '{prompt}'")

start_time = time.time()
try:
    response = requests.post(url, json=payload)
    end_time = time.time()
    
    if response.status_code == 200:
        result = response.json()
        print("\nResponse:")
        print(result.get("text"))
        print(f"\nTime taken: {end_time - start_time:.2f}s")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Request failed: {e}")

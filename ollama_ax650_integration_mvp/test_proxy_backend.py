#!/usr/bin/env python3
"""Test script for the Hybrid Proxy Backend (Direct).

Verifies that the proxy correctly forwards requests to the mock C++ server
and returns the generated text.
"""
import requests
import json
import time

PROXY_URL = "http://localhost:5002"

def test_health():
    print("Testing /health...")
    try:
        resp = requests.get(f"{PROXY_URL}/health")
        print(f"Status: {resp.status_code}")
        print(f"Body: {json.dumps(resp.json(), indent=2)}")
        assert resp.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        exit(1)

def test_generate():
    print("\nTesting /generate...")
    prompt = "Why is the sky blue?"
    payload = {
        "prompt": prompt,
        "max_tokens": 32,
        "temperature": 0.7
    }
    
    start_time = time.time()
    try:
        resp = requests.post(f"{PROXY_URL}/generate", json=payload)
        duration = time.time() - start_time
        
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"Response: {data.get('text')}")
            print(f"Duration: {duration:.2f}s")
        else:
            print(f"Error: {resp.text}")
            
    except Exception as e:
        print(f"Generate failed: {e}")
        exit(1)

if __name__ == "__main__":
    test_health()
    test_generate()

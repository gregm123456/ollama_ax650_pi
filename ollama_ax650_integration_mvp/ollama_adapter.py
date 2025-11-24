"""Tiny Ollama integration stub that calls the local AX650 backend HTTP API.

This is an example shim you can wire into Ollama's code paths (where Ollama calls
into an LLM) to forward requests to the Python backend. For an MVP, it's a
single function `generate(prompt)` that returns the backend response text.
"""
import os
import requests

BACKEND_URL = os.environ.get("AX650_BACKEND_URL", "http://localhost:5002")


def generate(prompt: str, max_tokens: int = 256) -> str:
    url = f"{BACKEND_URL}/generate"
    resp = requests.post(url, json={"prompt": prompt, "max_tokens": max_tokens}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("text", "")


if __name__ == "__main__":
    print(generate("Hello from Ollama adapter"))

#!/usr/bin/env python3
"""Standalone smoke test that mimics the fallback generator behavior without Flask.
"""
class DummyBackend:
    def __init__(self):
        self.model = "dummy-model"

    def load_model(self, path=None):
        self.model = path or self.model
        return {"status": "loaded", "model": self.model}

    def generate(self, prompt, max_tokens=32):
        return f"Echo: {prompt}"


if __name__ == "__main__":
    b = DummyBackend()
    print(b.load_model())
    print(b.generate("Hello from local smoke test"))

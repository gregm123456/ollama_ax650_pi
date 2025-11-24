#!/usr/bin/env python3
"""Minimal AX650/LLM8850 Python backend MVP.

Provides a tiny Flask HTTP API that wraps optional `pyaxcl`/`pyaxengine` bindings.
If the real bindings are not present, it falls back to a simple echo/dummy generator
so you can smoke-test integration locally on macOS or CI.
"""
import os
import json
from flask import Flask, request, jsonify

APP = Flask(__name__)


class AX650Backend:
    def __init__(self):
        self.impl = None
        self.model = None
        # try to import manufacturer python bindings
        try:
            import pyaxcl as axcl  # type: ignore
            self.impl = axcl
        except Exception:
            try:
                import pyaxengine as axeng  # type: ignore
                self.impl = axeng
            except Exception:
                self.impl = None

    def load_model(self, model_path: str = None):
        if self.impl is None:
            # dummy: record model path
            self.model = model_path or "dummy-model"
            return {"status": "loaded (dummy)", "model": self.model}

        # real binding path (placeholder - adapt to your binding's API)
        if hasattr(self.impl, "load_model"):
            self.model = self.impl.load_model(model_path)
            return {"status": "loaded", "model": str(self.model)}

        # fallback
        self.model = model_path or "ax650-model"
        return {"status": "loaded (fallback)", "model": self.model}

    def generate(self, prompt: str, max_tokens: int = 128):
        if self.impl is None:
            # deterministic simple echo so we can test end-to-end
            return f"Echo: {prompt}"

        # placeholder for a real generate call; adapt to your SDK
        if hasattr(self.impl, "generate"):
            return self.impl.generate(self.model, prompt, max_tokens=max_tokens)

        return f"(ax650-fallback) {prompt}"


BACKEND = AX650Backend()


@APP.route("/load", methods=["POST"])
def load_route():
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("model_path") or os.environ.get("AX650_MODEL_PATH")
    res = BACKEND.load_model(path)
    return jsonify(res)


@APP.route("/generate", methods=["POST"])
def generate_route():
    data = request.get_json(force=True, silent=True)
    if not data or "prompt" not in data:
        return jsonify({"error": "missing prompt"}), 400
    prompt = data["prompt"]
    max_tokens = int(data.get("max_tokens", 128))
    text = BACKEND.generate(prompt, max_tokens=max_tokens)
    return jsonify({"text": text})


def main():
    # load default model on start (best-effort)
    model_path = os.environ.get("AX650_MODEL_PATH")
    if model_path:
        BACKEND.load_model(model_path)
    # run Flask app
    APP.run(host="0.0.0.0", port=int(os.environ.get("AX650_PORT", 5002)))


if __name__ == "__main__":
    main()

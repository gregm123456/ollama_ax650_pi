#!/usr/bin/env python3
"""AX650/LLM8850 Hybrid Proxy Backend.

This service acts as a compatibility layer between Ollama and the manufacturer's
optimized C++ inference server (main_api_ax650).

Architecture:
  Ollama -> [Proxy (This Service)] -> [C++ Server (main_api_ax650)] -> NPU

Responsibilities:
  1. Manage C++ server lifecycle (start/stop/restart).
  2. Translate Ollama requests to C++ server API calls.
  3. Implement stateless-to-stateful logic (Reset -> Generate).
  4. Handle model loading and configuration.
"""
import os
import sys
import time
import logging
import subprocess
import requests
import signal
import re
import shutil
from flask import Flask, request, jsonify
from inference_engine import AX650Backend

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AX650Proxy")

APP = Flask(__name__)

# Configuration
RUNTIME_HOST = "127.0.0.1"
RUNTIME_PORT = 8000
RUNTIME_URL = f"http://{RUNTIME_HOST}:{RUNTIME_PORT}"
PROXY_PORT = int(os.environ.get("AX650_PORT", 5002))

# Subprocess state
RUNTIME_PROCESS = None
CURRENT_MODEL_PATH = os.environ.get("AX650_MODEL_PATH")
DEFAULT_SYSTEM_PROMPT = "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
CURRENT_CONTEXT_WINDOW_TOKENS = int(os.environ.get("AX650_MAX_CONTEXT_TOKENS", "1024"))
BACKEND_ENGINE = None


def get_backend_engine():
    """Return the parent-side backend engine used for configurable runtime state."""
    global BACKEND_ENGINE
    if BACKEND_ENGINE is None:
        BACKEND_ENGINE = AX650Backend()
        BACKEND_ENGINE.set_context_window(CURRENT_CONTEXT_WINDOW_TOKENS)
    return BACKEND_ENGINE


def apply_context_window(context_window_tokens, reset_runtime=True):
    """Update the active context window and reset runtime state if needed."""
    global CURRENT_CONTEXT_WINDOW_TOKENS

    try:
        value = int(context_window_tokens)
    except (TypeError, ValueError) as exc:
        raise ValueError("context_window_tokens must be an integer") from exc

    if value <= 0:
        raise ValueError("context_window_tokens must be greater than zero")

    CURRENT_CONTEXT_WINDOW_TOKENS = value
    os.environ["AX650_MAX_CONTEXT_TOKENS"] = str(value)

    engine = get_backend_engine()
    engine.set_context_window(value)

    if reset_runtime:
        try:
            requests.post(
                f"{RUNTIME_URL}/api/reset",
                json={"context_window_tokens": value},
                timeout=2,
            )
        except requests.exceptions.RequestException as exc:
            logger.info("Runtime reset skipped while applying context window: %s", exc)

    return CURRENT_CONTEXT_WINDOW_TOKENS

def start_runtime(model_path=None):
    """Start the C++ inference server (or mock) as a subprocess."""
    global RUNTIME_PROCESS, CURRENT_MODEL_PATH
    
    if RUNTIME_PROCESS:
        stop_runtime()
        
    if model_path:
        CURRENT_MODEL_PATH = model_path
        
    cwd = os.path.dirname(os.path.abspath(__file__))
    # Use the AXCL binary for M.2 card (Raspberry Pi 5 + AX650/LLM8850)
    real_binary = os.path.join(cwd, "main_api_axcl_aarch64")
    mock_script = os.path.join(cwd, "mock_main_api.py")
    
    cmd = []
    env = os.environ.copy()
    if CURRENT_MODEL_PATH:
        env["AX650_MODEL_PATH"] = CURRENT_MODEL_PATH
    
    # Check for real binary (and ensure it's not the LFS pointer)
    use_real = False
    if os.path.exists(real_binary) and os.access(real_binary, os.X_OK):
        # Check size to avoid LFS pointer (pointer is ~130 bytes)
        if os.path.getsize(real_binary) > 2000:
            use_real = True
            
    if use_real:
        logger.info(f"Launching REAL runtime: {real_binary}")
        
        # Prefer explicit model path from environment (/load request), then fall back
        # to known workspace locations.
        model_candidates = [
            CURRENT_MODEL_PATH,
            os.path.join(os.path.dirname(os.path.dirname(cwd)), "models", "Qwen3-4B"),
            os.path.join(
                os.path.dirname(os.path.dirname(cwd)),
                "ax650_raspberry_pi_services",
                "reference_projects_and_documentation",
                "Qwen3-4B",
                "qwen3-4b-ax650",
            ),
        ]
        model_base = None
        for candidate in model_candidates:
            if candidate and os.path.exists(candidate):
                model_base = candidate
                break

        if not model_base:
            logger.error(f"No valid model directory found from candidates: {model_candidates}")
            return False

        logger.info(f"Using model directory: {model_base}")

        def detect_runtime_device():
            """Detect an appropriate runtime device id.

            `axcl-smi` reports human-friendly device ids (1-based). The C++ runtime
            expects 0-based device ids. This helper runs `axcl-smi` (if available),
            parses the first `Device ID` line and returns (reported_id - 1).
            Falls back to 0 on any error.
            """
            axcl_bin = shutil.which("axcl-smi")
            if not axcl_bin:
                logger.warning("axcl-smi not found; defaulting to device 0")
                return "0"

            try:
                out = subprocess.check_output([axcl_bin, "info", "--cmm"], stderr=subprocess.STDOUT, text=True, timeout=5)
                # look for lines like: "Device ID           : 1 (0x1)"
                m = re.search(r"Device ID\s*:\s*(\d+)", out)
                if m:
                    reported = int(m.group(1))
                    runtime_id = max(0, reported - 1)
                    logger.info(f"Detected AXCL reported device {reported}; using runtime device {runtime_id}")
                    return str(runtime_id)
            except Exception as e:
                logger.warning(f"Failed to run axcl-smi to detect device: {e}; defaulting to 0")

            return "0"
        
        # Construct command with all required arguments
        device_id = detect_runtime_device()

        cmd = [
            real_binary,
            "--system_prompt", "You are Qwen, created by Alibaba Cloud. You are a helpful assistant.",
            "--template_filename_axmodel", f"{model_base}/qwen3_p128_l%d_together.axmodel",
            "--axmodel_num", "36",
            "--url_tokenizer_model", "http://127.0.0.1:12345",
            "--filename_post_axmodel", f"{model_base}/qwen3_post.axmodel",
            "--filename_tokens_embed", f"{model_base}/model.embed_tokens.weight.bfloat16.bin",
            "--tokens_embed_num", "151936",
            "--tokens_embed_size", "2560",
            "--use_mmap_load_embed", "1",
            "--devices", device_id
        ]
    else:
        logger.info(f"Launching MOCK runtime: {mock_script}")
        cmd = [sys.executable, mock_script]
        
    try:
        # Start process
        RUNTIME_PROCESS = subprocess.Popen(
            cmd, 
            cwd=cwd, 
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for health check
        logger.info("Waiting for runtime to initialize...")
        # AX650 model initialization can take time on cold start.
        for i in range(240):
            if RUNTIME_PROCESS.poll() is not None:
                # Process exited early
                out, err = RUNTIME_PROCESS.communicate()
                logger.error(f"Runtime exited early with code {RUNTIME_PROCESS.returncode}")
                logger.error(f"Stdout: {out.decode()}")
                logger.error(f"Stderr: {err.decode()}")
                return False
                
            try:
                # Try to connect to /api/stop (GET) as a ping
                requests.get(f"{RUNTIME_URL}/api/stop", timeout=0.5)
                logger.info("Runtime is up and responding!")
                
                # Start background thread to log runtime output?
                # For now, let's just leave it.
                return True
            except requests.exceptions.RequestException:
                time.sleep(0.5)
                
        logger.error("Runtime failed to start (timeout)")
        stop_runtime()
        return False
        
    except Exception as e:
        logger.error(f"Failed to launch runtime: {e}")
        return False

def stop_runtime():
    """Stop the C++ inference server."""
    global RUNTIME_PROCESS
    if RUNTIME_PROCESS:
        logger.info("Stopping runtime...")
        RUNTIME_PROCESS.terminate()
        try:
            RUNTIME_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Runtime did not exit gracefully, killing...")
            RUNTIME_PROCESS.kill()
        RUNTIME_PROCESS = None

@APP.route("/generate", methods=["POST"])
def proxy_generate():
    """Handle generation request from Ollama adapter."""
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")

    # Runtime /api/chat is reliable on current firmware. Use it directly.
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": data.get("max_tokens", 128),
        "temperature": data.get("temperature", 0.8),
        "top-p": data.get("top_p", 0.9),
        "top-k": data.get("top_k", 40),
    }

    max_retries = 20
    retry_delay = 0.2
    for attempt in range(max_retries):
        try:
            resp = requests.post(f"{RUNTIME_URL}/api/chat", json=payload, timeout=120)
            data_json = resp.json()

            # Runtime may transiently return busy; stop and retry.
            if data_json.get("error") == "llm is running":
                requests.get(f"{RUNTIME_URL}/api/stop", timeout=5)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return jsonify({"error": "Runtime remained busy after retries"}), 500

            resp.raise_for_status()
            text = data_json.get("message", "")
            # Strip reasoning wrapper tags for user-facing response.
            text = text.replace("<think>", "").replace("</think>", "").strip()
            return jsonify({"text": text})
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            logger.error(f"Failed to generate via /api/chat: {e}")
            return jsonify({"error": f"Failed to generate via runtime chat: {e}"}), 500

    return jsonify({"error": "Unexpected generation failure"}), 500

@APP.route("/config/context-window", methods=["GET"])
def get_context_window():
    """Return the active context window setting."""
    return jsonify({"context_window_tokens": CURRENT_CONTEXT_WINDOW_TOKENS})


@APP.route("/config/context-window", methods=["POST"])
def set_context_window():
    """Set the active context window for the parent-side backend."""
    data = request.get_json(force=True, silent=True) or {}
    context_window_tokens = data.get("context_window_tokens")
    if context_window_tokens is None:
        return jsonify({"error": "context_window_tokens is required"}), 400

    try:
        updated = apply_context_window(context_window_tokens)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"status": "ok", "context_window_tokens": updated})


@APP.route("/load", methods=["POST"])
def proxy_load():
    """Handle model load request."""
    data = request.get_json(force=True)
    path = data.get("model_path")
    if path:
        logger.info(f"Reloading model: {path}")
        if start_runtime(path):
            return jsonify({"status": "loaded", "model": path})
        else:
            return jsonify({"status": "error", "message": "Failed to start runtime"}), 500
    return jsonify({"status": "ok", "model": CURRENT_MODEL_PATH})

@APP.route("/health", methods=["GET"])
def health_check():
    """Proxy health check."""
    runtime_up = False
    try:
        requests.get(f"{RUNTIME_URL}/api/stop", timeout=0.5)
        runtime_up = True
    except:
        pass
        
    return jsonify({
        "status": "ok",
        "runtime_up": runtime_up,
        "model": CURRENT_MODEL_PATH,
        "mode": "proxy",
        "context_window_tokens": CURRENT_CONTEXT_WINDOW_TOKENS,
    })

def main():
    logger.info("="*60)
    logger.info("AX650 Hybrid Proxy Starting")
    logger.info("="*60)
    
    # Start runtime on launch
    if not start_runtime():
        logger.warning("Initial runtime launch failed, will retry on /load")
    
    try:
        APP.run(host="0.0.0.0", port=PROXY_PORT, debug=False, use_reloader=False)
    finally:
        stop_runtime()

if __name__ == "__main__":
    main()

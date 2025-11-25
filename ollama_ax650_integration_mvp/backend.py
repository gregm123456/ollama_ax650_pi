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
from flask import Flask, request, jsonify

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

def start_runtime(model_path=None):
    """Start the C++ inference server (or mock) as a subprocess."""
    global RUNTIME_PROCESS, CURRENT_MODEL_PATH
    
    if RUNTIME_PROCESS:
        stop_runtime()
        
    if model_path:
        CURRENT_MODEL_PATH = model_path
        
    cwd = os.path.dirname(os.path.abspath(__file__))
    real_binary = os.path.join(cwd, "main_api_ax650")
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
        # TODO: Construct proper arguments for real binary based on model path
        # For now, we assume the binary or wrapper script handles defaults or env vars
        # If using raw main_api_ax650, we need to pass --template_filename_axmodel etc.
        # This is a placeholder for Phase 2.
        cmd = [real_binary] 
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
        for i in range(20):
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
    
    # 1. Reset Runtime State (Stateless behavior)
    try:
        # We send empty system prompt to clear context
        requests.post(f"{RUNTIME_URL}/api/reset", json={"system_prompt": ""}, timeout=5)
    except Exception as e:
        logger.error(f"Failed to reset runtime: {e}")
        return jsonify({"error": f"Failed to reset runtime: {e}"}), 500
        
    # 2. Start Generation
    try:
        # Forward parameters
        # Map Ollama/Adapter params to C++ server params if needed
        # Adapter sends: prompt, max_tokens
        # C++ expects: prompt, max_tokens, temperature, top-p, top-k
        payload = {
            "prompt": prompt,
            "max_tokens": data.get("max_tokens", 128),
            "temperature": data.get("temperature", 0.8),
            "top-p": data.get("top_p", 0.9),
            "top-k": data.get("top_k", 40)
        }
        requests.post(f"{RUNTIME_URL}/api/generate", json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to start generation: {e}")
        return jsonify({"error": f"Failed to start generation: {e}"}), 500
        
    # 3. Poll for results (Streaming -> Accumulation)
    # Ollama adapter currently expects full text response.
    # We poll the provider until done.
    full_text = ""
    start_time = time.time()
    
    while True:
        try:
            resp = requests.get(f"{RUNTIME_URL}/api/generate_provider", timeout=5)
            if resp.status_code != 200:
                logger.error(f"Provider returned status {resp.status_code}")
                break
                
            rdata = resp.json()
            chunk = rdata.get("response", "")
            full_text += chunk
            
            if rdata.get("done", False):
                break
                
            # Timeout safety
            if time.time() - start_time > 120: # 2 min timeout
                logger.error("Generation timed out")
                break
                
            time.sleep(0.05) # Poll interval
            
        except Exception as e:
            logger.error(f"Error polling generation: {e}")
            return jsonify({"error": f"Error polling generation: {e}"}), 500
            
    return jsonify({"text": full_text})

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
        "mode": "proxy"
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

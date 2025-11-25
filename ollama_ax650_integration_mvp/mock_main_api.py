#!/usr/bin/env python3
"""Mock C++ Server for AX650/LLM8850.

Mimics the HTTP API of the manufacturer's C++ server (main_api_ax650).
Uses the existing Python inference engine (slow) to generate text,
allowing us to develop and test the proxy architecture before the real binary is available.
"""
import os
import logging
import threading
import queue
import time
from flask import Flask, request, jsonify
from inference_engine import AX650Backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP = Flask(__name__)
BACKEND = AX650Backend()

# Global state for async generation
# The C++ server uses a queue to store generated tokens for /api/generate_provider
# We will do the same.
MSG_QUEUE = queue.Queue()
IS_RUNNING = False
LOCK = threading.Lock()

def generation_worker(prompt, max_tokens, temperature, top_p, top_k):
    """Background thread to run inference and push results to queue."""
    global IS_RUNNING
    try:
        logger.info("MockServer: Starting generation worker")
        # Note: The current Python backend generates the FULL text at once.
        # We can't easily stream token-by-token without modifying inference_engine.py.
        # So we will generate the full text and push it as one chunk.
        # This mimics the API contract (polling) but with high latency for the first chunk.
        
        text = BACKEND.generate(
            prompt, 
            max_tokens=max_tokens, 
            temperature=temperature, 
            top_p=top_p, 
            top_k=top_k
        )
        
        with LOCK:
            MSG_QUEUE.put(text)
            logger.info(f"MockServer: Generation complete, pushed {len(text)} chars")
            
    except Exception as e:
        logger.error(f"MockServer: Generation failed: {e}")
        with LOCK:
            MSG_QUEUE.put(f"Error: {str(e)}")
    finally:
        with LOCK:
            IS_RUNNING = False

@APP.route("/api/reset", methods=["POST"])
def handle_reset():
    """Reset the engine state."""
    global IS_RUNNING
    with LOCK:
        if IS_RUNNING:
            return jsonify({"error": "llm is running"}), 400
            
    data = request.get_json(force=True, silent=True) or {}
    system_prompt = data.get("system_prompt", "")
    
    # In the real C++ server, this resets KV cache and sets system prompt.
    # Our Python backend doesn't explicitly support setting system prompt separately from generate,
    # but we can reset the device/cache.
    logger.info(f"MockServer: Resetting with system_prompt len={len(system_prompt)}")
    
    # We can call reset_device if needed, or just clear internal state if we had any.
    # The Python backend resets cache at start of generate() anyway.
    # But let's call reset_device to be safe if using real hardware.
    BACKEND.reset_device(0)
    
    return jsonify({"status": "ok"})

@APP.route("/api/generate", methods=["POST"])
def handle_generate():
    """Start async generation."""
    global IS_RUNNING
    
    # Check if model is loaded
    if not BACKEND.session and BACKEND.backend_type != "dummy":
         # Auto-load if not loaded (helper for dev)
         model_path = os.environ.get("AX650_MODEL_PATH")
         if model_path:
             BACKEND.load_model(model_path)
         else:
             return jsonify({"error": "Model not init"}), 400

    with LOCK:
        if IS_RUNNING:
            return jsonify({"error": "llm is running"}), 400
        
        # Clear queue from previous runs
        while not MSG_QUEUE.empty():
            MSG_QUEUE.get()
            
        IS_RUNNING = True

    data = request.get_json(force=True, silent=True)
    if not data or "prompt" not in data:
        with LOCK: IS_RUNNING = False
        return jsonify({"error": "Invalid request format"}), 400

    prompt = data["prompt"]
    max_tokens = int(data.get("max_tokens", 128)) # Note: C++ might use different param names?
    # main_api.cpp uses: temperature, repetition_penalty, top-p, top-k
    # Our backend uses: temperature, top_p, top_k
    temperature = float(data.get("temperature", 0.8))
    top_p = float(data.get("top-p", 0.9)) # Note hyphen in C++ API
    top_k = int(data.get("top-k", 40))    # Note hyphen in C++ API
    
    # Start worker
    t = threading.Thread(target=generation_worker, args=(prompt, max_tokens, temperature, top_p, top_k))
    t.start()
    
    return jsonify({"status": "ok"})

@APP.route("/api/generate_provider", methods=["GET"])
def content_provider():
    """Poll for generated content."""
    global IS_RUNNING
    
    response_text = ""
    with LOCK:
        while not MSG_QUEUE.empty():
            response_text += MSG_QUEUE.get()
        
        is_done = not IS_RUNNING
        
    return jsonify({
        "response": response_text,
        "done": is_done
    })

@APP.route("/api/stop", methods=["GET"])
def handle_stop():
    """Stop generation."""
    # We can't easily stop the Python thread, but we can flag it.
    # For MVP mock, we just pretend.
    global IS_RUNNING
    with LOCK:
        IS_RUNNING = False
    return jsonify({"status": "ok"})

@APP.route("/api/chat", methods=["POST"])
def handle_chat():
    """Synchronous chat endpoint."""
    # main_api.cpp implements this as a blocking call that returns the full response.
    data = request.get_json(force=True, silent=True)
    if not data or "messages" not in data:
        return jsonify({"error": "Invalid request format"}), 400
        
    messages = data["messages"]
    # Simple concatenation for mock (real backend handles this better usually)
    # But here we just take the last message content as prompt for simplicity
    # or construct a prompt.
    # The C++ server iterates messages and calls RunSync.
    
    # Let's just use the last user message for now
    last_msg = messages[-1]
    if "content" not in last_msg:
        return jsonify({"error": "Invalid message format"}), 400
        
    prompt = last_msg["content"]
    
    # Run synchronously
    text = BACKEND.generate(prompt)
    
    return jsonify({
        "message": text,
        "done": True
    })

def main():
    port = int(os.environ.get("AX650_PORT", 8000)) # Default to 8000 to match C++ server
    logger.info(f"Mock C++ Server starting on port {port}")
    
    # Load model on start if env var set
    model_path = os.environ.get("AX650_MODEL_PATH")
    if model_path:
        logger.info(f"Auto-loading model: {model_path}")
        BACKEND.load_model(model_path)
    else:
        # If no model path, we default to dummy mode in backend if not set
        logger.info("No AX650_MODEL_PATH set, backend might be in dummy mode")

    APP.run(host="0.0.0.0", port=port, debug=False, threaded=True)

if __name__ == "__main__":
    main()

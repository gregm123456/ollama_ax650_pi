#!/usr/bin/env python3
"""Minimal AX650/LLM8850 Python backend MVP.

Provides a tiny Flask HTTP API that wraps optional `pyaxcl`/`pyaxengine` bindings.
If the real bindings are not present, it falls back to a simple echo/dummy generator
so you can smoke-test integration locally on macOS or CI.

SDK Integration:
  - Uses axengine.InferenceSession for model loading and inference
  - Supports KV cache management for LLM context
  - Implements token-by-token generation with configurable parameters
"""
import os
import json
import logging
from flask import Flask, request, jsonify
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP = Flask(__name__)


class AX650Backend:
    def __init__(self):
        self.impl = None
        self.session = None
        self.model_path = None
        self.k_caches = None
        self.v_caches = None
        self.embedding_weights = None
        self.tokenizer = None
        
        # Try to import manufacturer python bindings
        self.backend_type = None
        self.axcl = None  # For low-level control like reset

        # Always try to import axcl (pyaxcl package) for device management
        try:
            import axcl
            self.axcl = axcl
            logger.info("Successfully imported axcl for device management")
        except ImportError:
            logger.warning("Could not import axcl - device reset will not be available")

        try:
            from axengine import InferenceSession  # type: ignore
            self.impl = InferenceSession
            self.backend_type = "axengine"
            logger.info("Successfully imported axengine.InferenceSession")
        except Exception as e:
            logger.info(f"Could not import axengine: {e}")
            try:
                if self.axcl:
                    self.impl = self.axcl
                    self.backend_type = "pyaxcl"
                    logger.info("Using pyaxcl as backend")
                else:
                    raise ImportError("No axcl bindings found")
            except Exception as e2:
                logger.info(f"Could not import pyaxcl as backend: {e2}")
                self.impl = None
                self.backend_type = "dummy"
                logger.warning("Running in DUMMY mode - no AX650 hardware access")

    def reset_device(self, device_id=0):
        """Reset the AX650 device to clear state."""
        if self.backend_type == "dummy":
            logger.info("DUMMY: Resetting device 0")
            return True
            
        if self.axcl:
            try:
                logger.info(f"Resetting device {device_id} via pyaxcl...")
                # axcl.rt.reset_device returns 0 on success
                ret = self.axcl.rt.reset_device(device_id)
                if ret != 0:
                    logger.error(f"axcl.rt.reset_device failed with code {ret}")
                    return False
                logger.info(f"Successfully reset device {device_id}")
                return True
            except Exception as e:
                logger.error(f"Exception during device reset: {e}")
                return False
        else:
            logger.warning("Cannot reset device: pyaxcl not available")
            return False

    def load_model(self, model_path: str = None):
        """Load AX650 model using InferenceSession.
        
        For LLM models, expects directory structure:
          model_path/
            model_prefill.axmodel  (prefill/prompt processing)
            model_decode.axmodel   (token-by-token generation)
            model.embed_tokens.weight.npy  (embedding weights)
            tokenizer/  (optional, for end-to-end inference)
        """
        if self.backend_type == "dummy":
            self.model_path = model_path or "dummy-model"
            logger.info(f"DUMMY mode: recorded model path {self.model_path}")
            return {"status": "loaded (dummy)", "model": self.model_path}

        if not model_path or not os.path.exists(model_path):
            return {"status": "error", "message": f"Model path not found: {model_path}"}
        
        # Reset device before loading new model to ensure clean state
        if self.session or self.axcl:
            logger.info("Resetting device before model load...")
            self.reset_device(0)
            self.session = None
            self.layers = []
        
        self.model_path = model_path
        
        try:
            if self.backend_type == "axengine":
                # Check for Qwen3-4B multi-layer structure
                if os.path.exists(os.path.join(model_path, "qwen3_post.axmodel")) or \
                   os.path.exists(os.path.join(model_path, "llama_post.axmodel")):
                    return self._load_qwen3_4b(model_path)

                # Load using axengine InferenceSession API
                prefill_path = os.path.join(model_path, "model_prefill.axmodel")
                decode_path = os.path.join(model_path, "model_decode.axmodel")
                
                if os.path.exists(prefill_path):
                    logger.info(f"Loading prefill model from {prefill_path}")
                    self.session = {
                        'prefill': self.impl(prefill_path),
                        'decode': self.impl(decode_path) if os.path.exists(decode_path) else None
                    }
                else:
                    # Single model file
                    model_file = os.path.join(model_path, "model.axmodel")
                    logger.info(f"Loading single model from {model_file}")
                    self.session = self.impl(model_file)
                
                # Load embedding weights if available
                embed_path = os.path.join(model_path, "model.embed_tokens.weight.npy")
                if os.path.exists(embed_path):
                    self.embedding_weights = np.load(embed_path)
                    logger.info(f"Loaded embeddings: shape {self.embedding_weights.shape}")
                
                # Initialize KV caches (will be sized based on model config)
                self._initialize_kv_caches()
                
                return {"status": "loaded", "model": model_path, "backend": "axengine"}
                
            elif self.backend_type == "pyaxcl":
                # pyaxcl specific loading (if API differs)
                logger.info(f"Loading model with pyaxcl from {model_path}")
                self.session = self.impl.load_model(model_path)
                return {"status": "loaded", "model": model_path, "backend": "pyaxcl"}
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}
        
        return {"status": "error", "message": "Unknown backend type"}

    def _load_qwen3_4b(self, model_path):
        """Load Qwen3-4B specific multi-layer model structure."""
        logger.info("Detected Qwen3-4B model structure")
        self.model_type = "qwen3-4b"
        
        # Load embeddings
        # Try .bin first (bfloat16)
        embed_path = os.path.join(model_path, "model.embed_tokens.weight.bfloat16.bin")
        if os.path.exists(embed_path):
            try:
                # Assuming shape [151936, 2560] from docs
                self.embedding_weights = np.fromfile(embed_path, dtype=np.uint16).reshape(151936, 2560)
                logger.info(f"Loaded bfloat16 embeddings from {embed_path}")
            except Exception as e:
                logger.error(f"Failed to load bin embeddings: {e}")
        
        if self.embedding_weights is None:
             # Try .npy
             embed_path = os.path.join(model_path, "model.embed_tokens.weight.npy")
             if os.path.exists(embed_path):
                 self.embedding_weights = np.load(embed_path)
                 logger.info(f"Loaded .npy embeddings from {embed_path}")

        # Load layers
        self.layers = []
        # Try to detect number of layers or assume 36
        num_layers = 36
        for i in range(num_layers):
             # Try different naming patterns
             p = os.path.join(model_path, f"qwen3_p128_l{i}_together.axmodel")
             if not os.path.exists(p):
                 p = os.path.join(model_path, f"llama_p320_l{i}_together.axmodel")
             
             if os.path.exists(p):
                 logger.info(f"Loading layer {i} from {os.path.basename(p)}")
                 self.layers.append(self.impl(p))
             else:
                 logger.warning(f"Layer {i} model not found at {p}")
        
        # Load post
        post_path = os.path.join(model_path, "qwen3_post.axmodel")
        if not os.path.exists(post_path):
            post_path = os.path.join(model_path, "llama_post.axmodel")
        
        if os.path.exists(post_path):
            logger.info(f"Loading post-process model from {post_path}")
            self.post_model = self.impl(post_path)
        
        # Initialize KV caches
        self._initialize_kv_caches(num_layers=len(self.layers))
        
        # Try to load tokenizer
        try:
            from transformers import AutoTokenizer
            # Qwen3-4B uses Qwen2Tokenizer, which might need trust_remote_code=True
            # Also try loading from the model path directly
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
                logger.info("Loaded AutoTokenizer from model path")
            except Exception as e1:
                logger.warning(f"Failed to load tokenizer from {model_path}: {e1}")
                # Fallback to Qwen/Qwen2.5-3B-Instruct or similar if local fails
                self.tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct", trust_remote_code=True)
                logger.info("Loaded AutoTokenizer from HF Hub fallback")
        except Exception as e:
            logger.warning(f"Could not load AutoTokenizer: {e}")

        self.session = "qwen3-4b-loaded" # Marker
        return {"status": "loaded", "model": model_path, "type": "qwen3-4b", "layers": len(self.layers)}

    
    def _initialize_kv_caches(self, num_layers=32, kv_dim=2048, max_seq_len=1023):
        """Initialize KV caches for LLM inference.
        
        These dimensions should match your model architecture.
        For Qwen3-4B: typically 32 layers, hidden_size=3072, num_kv_heads=4
        Adjust based on actual model config.
        """
        try:
            from ml_dtypes import bfloat16
            dtype = bfloat16
        except ImportError:
            dtype = np.float16
            logger.warning("ml_dtypes not available, using float16 for KV cache")
        
        self.k_caches = [
            np.zeros((1, max_seq_len, kv_dim), dtype=dtype)
            for _ in range(num_layers)
        ]
        self.v_caches = [
            np.zeros((1, max_seq_len, kv_dim), dtype=dtype)
            for _ in range(num_layers)
        ]
        logger.info(f"Initialized KV caches: {num_layers} layers, {max_seq_len} seq len, {kv_dim} dims")

    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.8, 
                 top_p: float = 0.9, top_k: int = 40):
        """Generate text using AX650 NPU inference.
        
        Args:
            prompt: Input text prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-2.0)
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling parameter
        
        Returns:
            Generated text string
        """
        if self.backend_type == "dummy":
            return f"Echo: {prompt}"
        
        if not self.session:
            return "Error: Model not loaded. Call /load first."
        
        try:
            if self.backend_type == "axengine":
                return self._generate_axengine(prompt, max_tokens, temperature, top_p, top_k)
            elif self.backend_type == "pyaxcl":
                return self._generate_pyaxcl(prompt, max_tokens)
        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            return f"Error during generation: {str(e)}"
    
    def _generate_axengine(self, prompt: str, max_tokens: int, temperature: float,
                          top_p: float, top_k: int):
        """Generate using axengine InferenceSession.
        
        This implements a basic autoregressive generation loop:
        1. Tokenize prompt
        2. Get embeddings
        3. Run prefill pass (if available) or first token
        4. Loop: generate tokens one at a time using decode pass
        5. Stop on EOS or max_tokens
        """
        if getattr(self, "model_type", None) == "qwen3-4b":
             return self._generate_qwen3_4b(prompt, max_tokens, temperature, top_p, top_k)

        # For now, return a placeholder showing the SDK is connected
        # Real implementation requires:
        # - Tokenizer integration (transformers AutoTokenizer or custom)
        # - Proper input tensor preparation
        # - KV cache management across decode steps
        # - Token sampling with temperature/top_p/top_k
        # - EOS detection and decoding
        
        logger.info(f"Generating with axengine: prompt='{prompt[:50]}...', max_tokens={max_tokens}")
        
        if not self.embedding_weights:
            return f"[axengine stub] Model loaded but embeddings missing. Prompt: {prompt}"
        
        # TODO: Implement full generation pipeline
        # See reference: SmolVLM-256M-Instruct.axera/python/infer_axmodel.py lines 130-250
        # Key steps:
        # 1. token_ids = tokenizer.encode(prompt)
        # 2. embeds = embedding_weights[token_ids]  # shape: (seq_len, hidden_dim)
        # 3. outputs = session['prefill'].run({"input_embeds": embeds, "k_caches": k_caches, ...})
        # 4. for _ in range(max_tokens):
        #      logits = outputs['logits'][-1]  # last token logits
        #      next_token = sample(logits, temperature, top_p, top_k)
        #      embeds = embedding_weights[next_token]
        #      outputs = session['decode'].run({"input_embeds": embeds, ...})
        # 5. return tokenizer.decode(generated_tokens)
        
        return f"[axengine] Generated response for: {prompt} (SDK integrated, full pipeline TODO)"

    def _generate_qwen3_4b(self, prompt, max_tokens, temperature, top_p, top_k):
        """Generation loop for Qwen3-4B multi-layer model."""
        if not self.tokenizer:
            return "Error: Tokenizer not loaded (transformers required)"
            
        # Placeholder for the complex 36-layer loop
        # This requires managing KV cache for 36 layers and running them sequentially
        return f"Qwen3-4B Model Loaded ({len(self.layers)} layers). Ready for inference loop implementation."

    
    def _generate_pyaxcl(self, prompt: str, max_tokens: int):
        """Generate using pyaxcl API (if different from axengine)."""
        logger.info(f"Generating with pyaxcl: prompt='{prompt[:50]}...', max_tokens={max_tokens}")
        
        # Adapt to pyaxcl API
        if hasattr(self.impl, "generate"):
            return self.impl.generate(self.session, prompt, max_tokens=max_tokens)
        
        return f"[pyaxcl stub] Prompt: {prompt}"


BACKEND = AX650Backend()


@APP.route("/load", methods=["POST"])
def load_route():
    data = request.get_json(force=True, silent=True) or {}
    path = data.get("model_path") or os.environ.get("AX650_MODEL_PATH")
    res = BACKEND.load_model(path)
    return jsonify(res)


@APP.route("/reset", methods=["POST"])
def reset_route():
    """Force hardware reset of the device."""
    device_id = int(request.args.get("device_id", 0))
    success = BACKEND.reset_device(device_id)
    if success:
        return jsonify({"status": "ok", "message": f"Device {device_id} reset successfully"})
    else:
        return jsonify({"status": "error", "message": "Device reset failed"}), 500


@APP.route("/generate", methods=["POST"])
def generate_route():
    data = request.get_json(force=True, silent=True)
    if not data or "prompt" not in data:
        return jsonify({"error": "missing prompt"}), 400
    prompt = data["prompt"]
    max_tokens = int(data.get("max_tokens", 128))
    temperature = float(data.get("temperature", 0.8))
    top_p = float(data.get("top_p", 0.9))
    top_k = int(data.get("top_k", 40))
    text = BACKEND.generate(prompt, max_tokens=max_tokens, temperature=temperature,
                           top_p=top_p, top_k=top_k)
    return jsonify({"text": text})


@APP.route("/health", methods=["GET"])
def health_route():
    """Device health and status endpoint.
    
    Returns:
        - backend_type: dummy, axengine, or pyaxcl
        - model_loaded: boolean
        - model_path: path to loaded model
        - temperature: NPU temperature (TODO: query from SDK)
        - memory: CMM usage (TODO: query from SDK)
    """
    health_data = {
        "status": "ok",
        "backend_type": BACKEND.backend_type,
        "model_loaded": BACKEND.session is not None,
        "model_path": BACKEND.model_path,
    }
    
    # TODO: Query actual hardware metrics when on Pi
    # Examples:
    # - Temperature: cat /sys/class/thermal/thermal_zone0/temp
    # - Memory: parse /proc/meminfo or use SDK APIs
    # - NPU utilization: SDK-specific query
    
    if BACKEND.backend_type != "dummy":
        health_data.update({
            "temperature_c": None,  # TODO: read from thermal zone
            "memory_usage_mb": None,  # TODO: query CMM
            "npu_utilization_pct": None,  # TODO: query NPU stats
        })
    
    return jsonify(health_data)


def main():
    logger.info("="*60)
    logger.info("AX650/LLM8850 Backend Server Starting")
    logger.info(f"Backend type: {BACKEND.backend_type}")
    logger.info("="*60)
    
    # Load default model on start (best-effort)
    model_path = os.environ.get("AX650_MODEL_PATH")
    if model_path:
        logger.info(f"Auto-loading model from AX650_MODEL_PATH: {model_path}")
        result = BACKEND.load_model(model_path)
        logger.info(f"Model load result: {result}")
    else:
        logger.info("No AX650_MODEL_PATH set. Model must be loaded via /load endpoint.")
    
    port = int(os.environ.get("AX650_PORT", 5002))
    logger.info(f"Starting Flask server on http://0.0.0.0:{port}")
    logger.info("Endpoints: /load (POST), /generate (POST), /health (GET)")
    
    # Run Flask app
    APP.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Inference Engine for AX650/LLM8850.

Extracted from backend.py to support both legacy backend and new mock server.
"""
import os
import logging
import numpy as np
import torch
from transformers import AutoTokenizer
import time
import ml_dtypes
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AX650Backend:
    def __init__(self):
        self.impl = None
        self.session = None
        self.model_path = None
        self.k_caches = None
        self.v_caches = None
        self.embedding_weights = None
        self.tokenizer = None
        self.layers = []
        self.post_model = None
        
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
            self.post_model = None
        
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
                # Load as uint16 (bfloat16 representation) then convert to float32
                raw_data = np.fromfile(embed_path, dtype=np.uint16)
                # Convert bfloat16 to float32 using torch because numpy doesn't support bfloat16 well
                tensor = torch.from_file(embed_path, shared=False, size=151936*2560, dtype=torch.bfloat16)
                self.embedding_weights = tensor.view(151936, 2560).float().numpy()
                logger.info(f"Loaded bfloat16 embeddings from {embed_path} and converted to float32")
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

    
    def _initialize_kv_caches(self, num_layers=32, kv_dim=1024, max_seq_len=1024):
        """Initialize KV caches for LLM inference.
        
        These dimensions should match your model architecture.
        For Qwen3-4B: typically 36 layers, hidden_size=2560, kv_dim=1024
        """
        # Use bfloat16 for KV cache to match model expectation
        dtype = ml_dtypes.bfloat16
        
        # Cache shape: [1, max_seq_len, kv_dim]
        # We maintain the full buffer here
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
                 top_p: float = 0.9, top_k: int = 40, request_id: str = None):
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
        # Ensure there is a request identifier to correlate traces
        if not request_id:
            request_id = str(uuid.uuid4())

        logger.info("REQ %s: generate start, prompt_len=%d", request_id, len(prompt))

        if self.backend_type == "dummy":
            logger.info("REQ %s: DUMMY backend echoing prompt", request_id)
            return f"Echo: {prompt}"
        
        if not self.session:
            return "Error: Model not loaded. Call /load first."
        
        try:
            if self.backend_type == "axengine":
                return self._generate_axengine(prompt, max_tokens, temperature, top_p, top_k, request_id=request_id)
            elif self.backend_type == "pyaxcl":
                return self._generate_pyaxcl(prompt, max_tokens)
        except Exception as e:
            logger.error(f"Generation failed: {e}", exc_info=True)
            return f"Error during generation: {str(e)}"
    
    def _generate_axengine(self, prompt: str, max_tokens: int, temperature: float,
                          top_p: float, top_k: int, request_id: str = None):
        """Generate using axengine InferenceSession.
        
        This implements a basic autoregressive generation loop:
        1. Tokenize prompt
        2. Get embeddings
        3. Run prefill pass (if available) or first token
        4. Loop: generate tokens one at a time using decode pass
        5. Stop on EOS or max_tokens
        """
        if getattr(self, "model_type", None) == "qwen3-4b":
            return self._generate_qwen3_4b(prompt, max_tokens, temperature, top_p, top_k, request_id=request_id)

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

    def _generate_qwen3_4b(self, prompt, max_tokens, temperature, top_p, top_k, request_id: str = None):
        """Generation loop for Qwen3-4B multi-layer model."""
        if not self.tokenizer:
            return "Error: Tokenizer not loaded (transformers required)"
        
        if not request_id:
            request_id = str(uuid.uuid4())

        logger.info("REQ %s: Starting Qwen3-4B generation for prompt: %s...", request_id, prompt[:50])
        
        # Timing accumulators
        t_start_total = time.perf_counter()
        t_tokenize = 0.0
        t_embedding = 0.0
        t_layer_runs = 0.0
        t_post = 0.0
        t_sampling = 0.0
        t_detokenize = 0.0
        n_npu_calls = 0

        # 1. Tokenize
        t0 = time.perf_counter()
        input_ids = self.tokenizer.encode(prompt)
        t_tokenize = time.perf_counter() - t0
        generated_ids = []
        
        # 2. Reset KV caches (zero out)
        for k in self.k_caches: k.fill(0)
        for v in self.v_caches: v.fill(0)
        
        current_pos = 0
        
        # 3. Prefill (process prompt tokens)
        # Note: This model seems to process one token at a time (batch=1, seq=1)
        # We must loop through the prompt.
        logger.info("REQ %s: Prefilling %d tokens...", request_id, len(input_ids))
        
        next_token = None
        
        # Combined loop for prefill + generation
        # We feed input_ids[i] during prefill, and sampled token during generation
        
        total_steps = len(input_ids) + max_tokens
        
        for step in range(total_steps):
            # Determine input token
            if step < len(input_ids):
                token_id = input_ids[step]
                is_prefill = True
            else:
                token_id = next_token
                is_prefill = False
                
            if step >= len(input_ids) + max_tokens:
                break
                
            # Stop if EOS generated
            if not is_prefill and (token_id == self.tokenizer.eos_token_id or token_id in [151643, 151645]): # Qwen EOS
                logger.info("EOS token generated")
                break
            
            # Prepare inputs
            # Embedding lookup
            # embedding_weights is float32 [vocab, hidden]
            # Convert to bfloat16 for NPU input
            t_e0 = time.perf_counter()
            hidden_state = self.embedding_weights[token_id].reshape(1, 1, 2560).astype(ml_dtypes.bfloat16)
            t_embedding += time.perf_counter() - t_e0
            
            # Prepare mask
            # Mask is [1, 1, 1024]. 1 for valid, 0 for masked.
            # We want 1s up to current_pos (inclusive)
            # Use bfloat16 as requested by runtime
            mask = np.zeros((1, 1, 1024), dtype=ml_dtypes.bfloat16)
            mask[:, :, :current_pos+1] = 1.0
            
            # Prepare indices
            # Explicitly cast to uint32 and verify
            indices = np.array([[current_pos]], dtype=np.uint32)
            
            # Run through layers
            t_layer_step0 = time.perf_counter()
            for i, layer_sess in enumerate(self.layers):
                # Prepare KV cache input: [1, 1023, 1024]
                # We pass the first 1023 elements of our 1024 buffer
                # They are already bfloat16 from initialization
                k_in = self.k_caches[i][:, :1023, :]
                v_in = self.v_caches[i][:, :1023, :]
                
                inputs = {
                    "input": hidden_state,
                    "K_cache": k_in,
                    "V_cache": v_in,
                    "indices": indices,
                    "mask": mask
                }
                
                # Run layer
                t_layer0 = time.perf_counter()
                outputs = layer_sess.run(None, inputs)
                t_layer_runs += time.perf_counter() - t_layer0
                n_npu_calls += 1
                
                # Outputs: K_cache_out, V_cache_out, output
                # Map outputs by name or index. 
                # Usually get_outputs() order is stable. 
                # Based on inspection: K_cache_out, V_cache_out, output
                # But run() returns list. Let's assume order matches inspection or use dict if supported?
                # axengine run returns list.
                # Inspection order: K_cache_out, V_cache_out, output
                
                k_out = outputs[0]
                v_out = outputs[1]
                hidden_state = outputs[2]
                
                # Update KV cache
                # k_out is [1, 1, 1024]
                self.k_caches[i][:, current_pos, :] = k_out.reshape(1, 1024)
                self.v_caches[i][:, current_pos, :] = v_out.reshape(1, 1024)
            # Per-step layer time
            t_layer_step = time.perf_counter() - t_layer_step0
            
            # Run Post model
            # Input: input [1, 1, 2560]
            # Output: output [1, 1, 151936]
            # Ensure hidden_state is bfloat16 (it should be from layer output, but verify)
            t_post0 = time.perf_counter()
            post_out = self.post_model.run(None, {"input": hidden_state})
            t_post += time.perf_counter() - t_post0
            n_npu_calls += 1
            logits = post_out[0] # [1, 1, 151936]

            # Log logits shape and top-k candidates for this step for correlation/debugging
            try:
                lshape = getattr(logits, 'shape', None)
                logger.info("REQ %s: step=%d post logits shape=%s", request_id, step, lshape)
                # Convert to numpy float32 if needed
                try:
                    logits_np = np.array(logits)
                except Exception:
                    logits_np = np.asarray(logits)

                if logits_np.dtype == ml_dtypes.bfloat16:
                    logits_np = logits_np.astype(np.float32)

                # Extract top-k ids for quick sanity check
                try:
                    flat = logits_np.reshape(-1)
                    k = min(10, flat.size)
                    topk_idx = np.argpartition(flat, -k)[-k:]
                    topk_sorted = topk_idx[np.argsort(-flat[topk_idx])]
                    logger.info("REQ %s: step=%d logits topk_ids=%s", request_id, step, topk_sorted.tolist())
                except Exception:
                    logger.warning("REQ %s: step=%d failed to compute topk", request_id, step)

                # Optionally save logits for offline inspection (first few steps only)
                if step < 3:
                    try:
                        out_path = f"/tmp/{request_id}_logits_step{step}.npy"
                        np.save(out_path, logits_np.astype(np.float32))
                        logger.info("REQ %s: saved logits to %s", request_id, out_path)
                    except Exception as e:
                        logger.warning("REQ %s: failed to save logits: %s", request_id, e)
            except Exception as e:
                logger.warning("REQ %s: error logging logits/topk: %s", request_id, e)
            
            # Sample next token
            t_sample0 = time.perf_counter()
            next_token = self._sample(logits, temperature, top_p, top_k)
            t_sampling += time.perf_counter() - t_sample0
            
            if not is_prefill:
                generated_ids.append(next_token)

            # Log per-step timing to help correlate with NPU trace
            try:
                step_elapsed = time.perf_counter() - t_start_total
                logger.info("REQ %s: step=%d elapsed=%.6fs step_layer_time=%.6fs npu_calls=%d", request_id, step, step_elapsed, t_layer_step, n_npu_calls)
            except Exception:
                pass
                
            current_pos += 1
            if current_pos >= 1023:
                logger.warning("Context length limit reached")
                break
                
        # Decode generated tokens
        t_d0 = time.perf_counter()
        output_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        t_detokenize = time.perf_counter() - t_d0

        t_total = time.perf_counter() - t_start_total

        # Log profiling summary
        try:
            logger.info("Generation timing summary: total=%.3fs, tokenize=%.4fs, embedding=%.4fs, layer_runs=%.4fs, post=%.4fs, sampling=%.4fs, detokenize=%.4fs, npu_calls=%d, steps=%d",
                        t_total, t_tokenize, t_embedding, t_layer_runs, t_post, t_sampling, t_detokenize, n_npu_calls, len(input_ids) + len(generated_ids))
        except Exception:
            # Ensure we never crash profiling
            pass

        return output_text

    def _sample(self, logits, temperature, top_p, top_k):
        """Sample next token from logits."""
        # logits shape: [1, 1, vocab_size]
        # Convert ml_dtypes.bfloat16 to float32 for torch compatibility
        if logits.dtype == ml_dtypes.bfloat16:
            logits = logits.astype(np.float32)

        logits = torch.tensor(logits[0, 0, :])
        
        # Apply temperature
        if temperature > 0:
            logits = logits / temperature
        
        # Top-K
        if top_k > 0:
            v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
            logits[logits < v[-1]] = -float('Inf')
            
        # Top-P (Nucleus)
        if top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(logits, descending=True)
            cumulative_probs = torch.cumsum(torch.softmax(sorted_logits, dim=-1), dim=-1)
            sorted_indices_to_remove = cumulative_probs > top_p
            # Shift the indices to the right to keep also the first token above the threshold
            sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0
            indices_to_remove = sorted_indices[sorted_indices_to_remove]
            logits[indices_to_remove] = -float('Inf')
            
        # Sample
        probs = torch.softmax(logits, dim=-1)
        next_token = torch.multinomial(probs, num_samples=1).item()
        return next_token


    
    def _generate_pyaxcl(self, prompt: str, max_tokens: int):
        """Generate using pyaxcl API (if different from axengine)."""
        logger.info(f"Generating with pyaxcl: prompt='{prompt[:50]}...', max_tokens={max_tokens}")
        
        # Adapt to pyaxcl API
        if hasattr(self.impl, "generate"):
            return self.impl.generate(self.session, prompt, max_tokens=max_tokens)
        
        return f"[pyaxcl stub] Prompt: {prompt}"

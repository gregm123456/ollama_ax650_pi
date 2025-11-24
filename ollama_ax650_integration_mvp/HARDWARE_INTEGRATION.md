# AX650 Hardware Integration Guide

This document provides detailed instructions for integrating the AX650/LLM8850 NPU SDK with the Ollama backend.

## Overview

The backend uses the **axengine** Python API (PyAXEngine) to interface with AX650 hardware. The implementation follows the patterns from the reference projects in `ax650_raspberry_pi_services/reference_projects_and_documentation/`.

## SDK API Reference

### axengine.InferenceSession

The primary interface for model loading and inference:

```python
from axengine import InferenceSession

# Load a model
session = InferenceSession.load_from_model("path/to/model.axmodel")

# Run inference
outputs = session.run({"input_name": input_tensor})
```

### Supported Providers

- **AxEngineExecutionProvider**: On-board NPU (Raspberry Pi)
- **AXCLRTExecutionProvider**: M.2 accelerator card (if using compute card)

## Model Structure for LLMs

The backend expects LLM models in the following structure:

```
model_directory/
├── model_prefill.axmodel       # Prompt processing model
├── model_decode.axmodel         # Token generation model
├── model.embed_tokens.weight.npy  # Token embedding weights
├── config.json                  # Model configuration
└── tokenizer/                   # Tokenizer files (if using transformers)
    ├── tokenizer.json
    └── tokenizer_config.json
```

### Alternative: Single Model

For simpler models, a single `model.axmodel` file can be used instead of separate prefill/decode models.

## Implementation Steps

### Step 1: Install Dependencies

On the Raspberry Pi:

```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
source .venv/bin/activate

# Install PyAXEngine (get latest from https://github.com/AXERA-TECH/pyaxengine/releases)
pip install axengine-0.1.3-py3-none-any.whl

# Install additional dependencies
pip install ml-dtypes numpy transformers
```

### Step 2: Prepare Model Files

1. **Obtain AX650-optimized model:**
   - Use Pulsar2 toolchain to convert your model
   - Or use pre-converted models from AXERA-TECH repositories
   - Recommended starting point: Qwen3-4B-Instruct (already in reference_projects)

2. **Verify model structure:**

```bash
ls -lh /path/to/your/model/
# Should see .axmodel files and embedding weights
```

3. **Set environment variable:**

```bash
export AX650_MODEL_PATH=/path/to/your/model
```

### Step 3: Complete the Generation Pipeline

The current `backend.py` has the SDK integration structure in place but needs the full generation loop implemented. Here's what to add:

#### A. Tokenizer Integration

In `backend.py`, add tokenizer loading in `load_model()`:

```python
def load_model(self, model_path: str = None):
    # ... existing code ...
    
    # Load tokenizer
    try:
        from transformers import AutoTokenizer
        tokenizer_path = os.path.join(model_path, "tokenizer")
        if os.path.exists(tokenizer_path):
            self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
            logger.info("Loaded tokenizer")
    except Exception as e:
        logger.warning(f"Could not load tokenizer: {e}")
```

#### B. Token Sampling

Add sampling utilities (based on reference implementation):

```python
def _sample_token(self, logits: np.ndarray, temperature: float, top_p: float, top_k: int) -> int:
    """Sample next token from logits using temperature, top-p, and top-k."""
    # Apply temperature
    logits = logits.astype(np.float32) / temperature
    
    # Top-k filtering
    if top_k > 0:
        indices = np.argpartition(logits, -top_k)[-top_k:]
        filtered_logits = np.full_like(logits, -np.inf)
        filtered_logits[indices] = logits[indices]
        logits = filtered_logits
    
    # Softmax
    exp_logits = np.exp(logits - np.max(logits))
    probs = exp_logits / np.sum(exp_logits)
    
    # Top-p (nucleus) sampling
    sorted_indices = np.argsort(probs)[::-1]
    sorted_probs = probs[sorted_indices]
    cumsum = np.cumsum(sorted_probs)
    cutoff_idx = np.searchsorted(cumsum, top_p)
    
    # Sample from filtered distribution
    nucleus_indices = sorted_indices[:cutoff_idx + 1]
    nucleus_probs = probs[nucleus_indices]
    nucleus_probs = nucleus_probs / nucleus_probs.sum()
    
    return np.random.choice(nucleus_indices, p=nucleus_probs)
```

#### C. Complete Generation Loop

Replace the stub in `_generate_axengine()`:

```python
def _generate_axengine(self, prompt: str, max_tokens: int, temperature: float,
                      top_p: float, top_k: int):
    """Full autoregressive generation with KV cache."""
    
    if not self.tokenizer:
        return f"Error: Tokenizer not loaded for model {self.model_path}"
    
    # 1. Tokenize input
    token_ids = self.tokenizer.encode(prompt, add_special_tokens=True)
    logger.info(f"Tokenized prompt: {len(token_ids)} tokens")
    
    # 2. Get embeddings
    try:
        from ml_dtypes import bfloat16
        embeds = np.take(self.embedding_weights, token_ids, axis=0).astype(bfloat16)
    except ImportError:
        embeds = np.take(self.embedding_weights, token_ids, axis=0).astype(np.float16)
    
    embeds = np.expand_dims(embeds, axis=0)  # Add batch dimension
    
    # 3. Prefill pass (process entire prompt)
    if isinstance(self.session, dict) and 'prefill' in self.session:
        logger.info("Running prefill pass")
        prefill_outputs = self.session['prefill'].run({
            'input_embeds': embeds,
            'k_caches': self.k_caches,
            'v_caches': self.v_caches
        })
        # Update KV caches with prefill outputs
        for i, (k, v) in enumerate(zip(prefill_outputs['k_cache'], prefill_outputs['v_cache'])):\n            self.k_caches[i] = k
            self.v_caches[i] = v
        
        last_logits = prefill_outputs['logits'][:, -1, :]  # Last token logits
    else:
        # Single-pass model
        outputs = self.session.run({'input_embeds': embeds})
        last_logits = outputs['logits'][:, -1, :]
    
    # 4. Decode loop (generate tokens one by one)
    generated_ids = []
    eos_token_id = self.tokenizer.eos_token_id
    
    for step in range(max_tokens):
        # Sample next token
        next_token_id = self._sample_token(last_logits[0], temperature, top_p, top_k)
        generated_ids.append(next_token_id)
        
        # Check for EOS
        if next_token_id == eos_token_id:
            logger.info(f"EOS reached at step {step}")
            break
        
        # Get embedding for next token
        next_embed = np.take(self.embedding_weights, [next_token_id], axis=0)
        next_embed = np.expand_dims(next_embed, axis=0)
        
        # Decode pass (single token)
        if isinstance(self.session, dict) and 'decode' in self.session:
            decode_outputs = self.session['decode'].run({
                'input_embeds': next_embed,
                'k_caches': self.k_caches,
                'v_caches': self.v_caches
            })
            # Update KV caches
            for i, (k, v) in enumerate(zip(decode_outputs['k_cache'], decode_outputs['v_cache'])):\n                self.k_caches[i] = k
                self.v_caches[i] = v
            last_logits = decode_outputs['logits'][:, -1, :]
        else:
            outputs = self.session.run({'input_embeds': next_embed})
            last_logits = outputs['logits'][:, -1, :]
    
    # 5. Decode tokens to text
    generated_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
    logger.info(f"Generated {len(generated_ids)} tokens")
    
    return generated_text
```

### Step 4: Test on Hardware

1. **Start the backend:**

```bash
export AX650_MODEL_PATH=/path/to/qwen3-4b-model
export AX650_PORT=5002
.venv/bin/python backend.py
```

2. **Test generation:**

```bash
curl -X POST http://localhost:5002/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is artificial intelligence?",
    "max_tokens": 100,
    "temperature": 0.8,
    "top_p": 0.9
  }'
```

3. **Check health:**

```bash
curl http://localhost:5002/health
```

### Step 5: Add Hardware Monitoring

Implement actual hardware metrics in the `/health` endpoint:

```python
def _get_npu_temperature(self):
    """Read NPU temperature from thermal zone."""
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_millidegrees = int(f.read().strip())
            return temp_millidegrees / 1000.0
    except Exception as e:
        logger.warning(f"Could not read temperature: {e}")
        return None

def _get_memory_usage(self):
    """Get memory usage statistics."""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            mem_info = {}
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    mem_info[key.strip()] = value.strip()
            
            total_kb = int(mem_info.get('MemTotal', '0').split()[0])
            available_kb = int(mem_info.get('MemAvailable', '0').split()[0])
            used_mb = (total_kb - available_kb) / 1024
            return used_mb
    except Exception as e:
        logger.warning(f"Could not read memory: {e}")
        return None
```

Then update the health route:

```python
@APP.route("/health", methods=["GET"])
def health_route():
    health_data = {
        "status": "ok",
        "backend_type": BACKEND.backend_type,
        "model_loaded": BACKEND.session is not None,
        "model_path": BACKEND.model_path,
    }
    
    if BACKEND.backend_type != "dummy":
        health_data.update({
            "temperature_c": BACKEND._get_npu_temperature(),
            "memory_usage_mb": BACKEND._get_memory_usage(),
            # TODO: Add NPU-specific metrics from SDK if available
        })
    
    return jsonify(health_data)
```

## Troubleshooting

### Model Loading Issues

**Problem:** `Model load result: {'status': 'error', 'message': '...'}`

**Solutions:**
- Verify model path exists and contains .axmodel files
- Check file permissions
- Ensure model is compatible with your NPU version
- Check logs for specific SDK error messages

### Import Errors

**Problem:** `Could not import axengine`

**Solutions:**
- Verify PyAXEngine wheel is installed: `pip list | grep axengine`
- Check Python version compatibility (requires Python >= 3.8)
- Ensure running on aarch64 architecture (AX650 hardware)

### Performance Issues

**Problem:** Slow inference times

**Solutions:**
- Verify NPU is being used (check logs for "AxEngineExecutionProvider")
- Monitor temperature (throttling may occur above 85°C)
- Check KV cache size matches model requirements
- Consider using separate prefill/decode models for better performance

### Memory Issues

**Problem:** Out of memory errors

**Solutions:**
- Reduce `max_seq_len` in KV cache initialization
- Use bfloat16 instead of float32 where possible
- Monitor CMM usage via `/health` endpoint
- Consider smaller model variant

## Performance Benchmarks

Expected performance on Raspberry Pi 5 with AX650:

- **Qwen3-4B-Instruct:**
  - Prefill: 100-200 tokens/sec
  - Decode: 15-25 tokens/sec
  - First token latency: 50-100ms

- **Smaller models (1B-2B):**
  - Decode: 30-50 tokens/sec

## Next Steps

1. **Complete the generation pipeline** using the code snippets above
2. **Test with real hardware** on Raspberry Pi
3. **Benchmark performance** and tune parameters
4. **Add error recovery** for hardware failures
5. **Integrate with Ollama** using `ollama_adapter.py`

## Reference Documentation

- **PyAXEngine**: `ax650_raspberry_pi_services/reference_projects_and_documentation/PyAXEngine/`
- **Example implementations**: `SmolVLM-256M-Instruct.axera/python/infer_axmodel.py`
- **SDK docs**: `reference_projects_and_documentation/axcl-docs/`
- **Pulsar2 (model conversion)**: `reference_projects_and_documentation/pulsar2-docs/`

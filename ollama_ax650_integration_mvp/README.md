# Ollama AX650 Integration MVP

This directory contains a minimal Python-based backend MVP to integrate AX650/LLM8850 models with Ollama.

## Architecture

The MVP consists of:
- **`backend.py`** — Flask HTTP API exposing `/load` and `/generate` endpoints. Uses `pyaxcl`/`pyaxengine` if available, otherwise runs in dummy mode for local testing.
- **`ollama_adapter.py`** — Python shim to integrate the backend with Ollama's inference pipeline.
- **`requirements.txt`** — Minimal dependencies (Flask, requests).
- **`run_backend.sh`** — Backend runner script.
- **`test_generate.sh`** — Curl-based smoke test.

## Current Status

✅ **MVP Setup Complete** (as of Nov 23, 2025):
- Virtual environment created and dependencies installed
- Backend server running successfully on port 5002
- Dummy implementation tested and working (`/generate` endpoint returns `Echo: <prompt>`)
- Ready for integration with real AX650 SDK bindings

## Quickstart (Local Development)

1. **Create a virtualenv and install deps:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Run the backend locally** (dummy mode if `pyaxcl` not installed):

```bash
./run_backend.sh
```

3. **Test with the included script:**

```bash
./test_generate.sh
```

Or test directly with Python:

```bash
.venv/bin/python -c "import requests; print(requests.post('http://localhost:5002/generate', json={'prompt':'ping','max_tokens':16}).json())"
```

## Deployment on Raspberry Pi 5 with AX650 Hardware

### Prerequisites
- Ubuntu image for Raspberry Pi 5
- Python 3.10+
- AX650/LLM8850 hardware installed
- Manufacturer Python bindings (`pyaxcl` or `pyaxengine`)

### Setup Steps

1. **Clone and set up environment:**

```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Install manufacturer bindings:**

```bash
# Install the manufacturer-provided package (check their docs for exact name)
pip install pyaxcl  # or pyaxengine, depending on your SDK version
```

3. **Configure environment:**

```bash
export AX650_MODEL_PATH=/path/to/your/ax650/model
export AX650_PORT=5002
```

4. **Run the backend:**

```bash
.venv/bin/python backend.py
```

5. **Test on Pi:**

```bash
.venv/bin/python -c "import requests; print(requests.post('http://localhost:5002/generate', json={'prompt':'Hello AX650','max_tokens':64}).json())"
```

## Next Steps

### On Raspberry Pi Hardware

1. **Replace dummy implementation with real SDK calls:**
   - Edit `backend.py` in the `AX650Backend.generate()` method
   - Replace the fallback logic with actual `pyaxcl`/`pyaxengine` inference API calls
   - Keep the same `/generate` and `/load` endpoint signatures

2. **Add device health monitoring:**
   - Implement temperature checks
   - Add CMM (memory) monitoring
   - Add NPU utilization tracking
   - Expose a `/health` endpoint

3. **Integrate with Ollama:**
   - **Option A (Quick Path):** Run backend as HTTP service, modify Ollama to call it via `ollama_adapter.py`
   - **Option B (Advanced):** Implement native Ollama backend plugin that links AXCL SDK in-process

### Code Structure for Real SDK Integration

In `backend.py`, update the `AX650Backend` class methods:

```python
def load_model(self, model_path: str = None):
    """Load model using real SDK API"""
    if self.impl is not None:
        # Replace with actual SDK model loading
        # Example: self.model = self.impl.Model(model_path)
        pass
    # ... rest of implementation

def generate(self, prompt: str, max_tokens: int = 128):
    """Generate text using real SDK API"""
    if self.impl is not None:
        # Replace with actual SDK inference call
        # Example: return self.impl.generate(self.model, prompt, max_tokens)
        pass
    # ... fallback implementation
```

## Testing

**Local (Dummy Mode):**
```bash
# Backend should return: {"text": "Echo: test"}
curl -X POST http://localhost:5002/generate -H "Content-Type: application/json" -d '{"prompt":"test","max_tokens":16}'
```

**On Pi (Real Hardware):**
```bash
# Backend should return actual model inference
curl -X POST http://localhost:5002/generate -H "Content-Type: application/json" -d '{"prompt":"What is AI?","max_tokens":128}'
```

## Troubleshooting

- **Import errors for pyaxcl/pyaxengine:** These are expected on non-Pi systems. The backend will run in dummy mode.
- **Port already in use:** Change `AX650_PORT` environment variable.
- **Model not loading:** Verify `AX650_MODEL_PATH` points to a valid model file/directory.

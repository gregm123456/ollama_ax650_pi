# Quick take-home (clone on the Pi — do this first)

To set up the environment on the Raspberry Pi, clone the main repository and recursively initialize all submodules. This ensures you get the correct versions of the AX650 services and the Ollama fork.

1. **Clone the repository:**

```bash
git clone https://github.com/gregm123456/ollama_ax650_pi.git
cd ollama_ax650_pi
```

2. **Initialize and update submodules:**

This command will fetch the `ax650_raspberry_pi_services` and `ollama` submodules, and then recursively fetch all nested submodules (including the reference projects and hardware documentation).

```bash
git submodule update --init --recursive
```

*Note: If you encounter authentication prompts for public repositories, you can try:*
```bash
GIT_TERMINAL_PROMPT=1 git submodule update --init --recursive
```

3. **Verify structure:**

After the update, you should see populated directories for:
- `ax650_raspberry_pi_services/` (contains `coyote_interactive`, `reference_projects_and_documentation`, etc.)
- `ollama/` (the Ollama source code)
- `ollama_ax650_integration_mvp/` (the Python integration code)

# Raspberry Pi Handoff & Next Steps

Prerequisites on Pi:
- Ubuntu (target image for the Pi)
- Python 3.10+ and build tools
- Manufacturer Python bindings (e.g., `pyaxcl` or `pyaxengine`) installed on the Pi

Quick checklist to perform on the Pi:

1. Clone repository on Pi:

```bash
git clone <this-repo> && cd <repo>/ollama_ax650_integration_mvp
```

2. Create and activate a venv, install manufacturer binding and deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# install manufacturer-provided package if available
pip install pyaxcl || pip install pyaxengine
```

3. Set model path and run backend:

```bash
export AX650_MODEL_PATH=/path/to/ax650/model
export AX650_PORT=5002
.venv/bin/python backend.py
```

4. Test generation locally on Pi:

```bash
.venv/bin/python -c "import requests; print(requests.post('http://localhost:5002/generate', json={'prompt':'ping','max_tokens':16}).json())"
```

5. Replace dummy generation with real SDK calls:

- Edit `ollama_ax650_integration_mvp/backend.py` and replace the fallback `generate` implementation with the appropriate calls to `pyaxcl` / `pyaxengine` model inference API. Keep the same `/generate` and `/load` endpoints so the Ollama adapter does not need to change.

6. Integrate into Ollama:

- Option A (recommended quick path): Keep the backend as an HTTP service on the Pi and modify Ollama to call the local service (via `ollama_adapter.py` or a Go/CPP HTTP client) when routing requests for the AX650-optimized model.
- Option B (advanced): Implement a native Ollama backend plugin that links the AXCL SDK in-process. This requires C++/Go changes in `ollama/` and is more invasive.

7. Device and health checks (post-MVP):

- Add periodic temperature, CMM, and utilization queries using manufacturer APIs and expose a `/health` endpoint.

Notes:
- The repository includes fallbacks to run and test locally without the Pi or manufacturer bindings. The Pi steps above are intentionally minimal — once the binding APIs are available on Pi, updating `backend.py` is straightforward.

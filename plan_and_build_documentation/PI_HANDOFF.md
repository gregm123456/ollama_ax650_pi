# Quick take-home (clone on the Pi — do this first)

Before cloning on the Raspberry Pi, follow these exact, safe steps to avoid submodule pointer/commit problems:

- Clone the repository normally (do NOT use shallow clones for submodules):

```bash
git clone https://github.com/gregm123456/ollama_ax650_pi.git
cd ollama_ax650_pi
```

- Fetch and make sure the local top-level exactly matches GitHub (this avoids local pointer drift):

```bash
git fetch origin --prune
git reset --hard origin/main
```

- Sync and initialise submodules the safe way (no depth/shallow):

```bash
git submodule sync --recursive
GIT_TERMINAL_PROMPT=1 git submodule update --init --recursive --force
```

- If you see an error like "it did not contain <sha>" for a nested submodule, do not mass-commit pointer changes. Instead, inspect and safely recover:

```bash
# in the problematic submodule dir
cd path/to/problematic/submodule
git remote -v
git fetch --all --tags --prune
# try to checkout the recorded SHA first, otherwise pick a reachable branch tip
git checkout <recorded-sha> || git checkout origin/master || git checkout origin/main
cd -
# then re-run
GIT_TERMINAL_PROMPT=1 git submodule update --init --recursive
```

- Only update and push submodule pointer changes in the superproject when you intentionally want to pin a new upstream tip. To publish a safe pointer update:

```bash
# commit inside the submodule (if you changed its gitlink), then in the parent:
git add path/to/submodule
git commit -m "Update <submodule> pointer to reachable tip"
git push origin HEAD:main
```

- Authentication: ensure the Pi has access to remotes (SSH keys or HTTPS credentials) or set `GIT_TERMINAL_PROMPT=1` to allow interactive auth.

- Summary notes:
	- Do not use `--depth` for submodule init unless you explicitly know the recorded commit exists in the shallow fetch. Shallow fetches caused the missing-commit errors we fixed locally.
	- Prefer fetch+checkout inside the offending submodule over wide-ranging top-level pointer commits.
	- If you need me to make the repo always reference branch tips instead of recorded SHAs, say so and I'll prepare a small script and CI check.

# Raspberry Pi Handoff & Next Steps

Prerequisites on Pi:
- Ubuntu (target image for the Pi)
- Python 3.10+ and build tools
- Manufacturer Python bindings (e.g., `pyaxcl` or `pyaxengine`) installed on the Pi

Quick checklist to perform on the Pi:

1. Clone repository on Pi:

```bash
git clone https://github.com/gregm123456/ollama_ax650_pi.git && cd ollama_ax650_pi
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

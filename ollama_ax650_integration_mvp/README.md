# Ollama AX650 Integration MVP

This directory contains a minimal Python-based backend MVP to integrate AX650/LLM8850 models with Ollama.

Files:
- `backend.py` — Flask app exposing `/load` and `/generate` endpoints. Uses `pyaxcl`/`pyaxengine` if available, otherwise a dummy echo generator.
- `requirements.txt` — minimal dependencies.
- `run_backend.sh` — simple runner.
- `test_generate.sh` — curl-based smoke test.

Quickstart:

1. Create a virtualenv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the backend locally (dummy mode if `pyaxcl` not installed):

```bash
./run_backend.sh
```

3. Test with the included script:

```bash
./test_generate.sh
```

On the Raspberry Pi, install the manufacturer's Python binding (`pyaxcl`), set `AX650_MODEL_PATH` environment variable, and run the service.

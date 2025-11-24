# Quick Reference: Hardware Integration

## 🚀 Quick Start (Raspberry Pi)

```bash
# Install SDK
pip install axengine-0.1.3-py3-none-any.whl
pip install -r requirements-hardware.txt

# Set model path and start
export AX650_MODEL_PATH=/path/to/model
python backend.py
```

## 🧪 Test Commands

```bash
# Health check
curl http://localhost:5002/health

# Load model
curl -X POST http://localhost:5002/load \
  -H "Content-Type: application/json" \
  -d '{"model_path":"/path/to/model"}'

# Generate text
curl -X POST http://localhost:5002/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","max_tokens":50}'

# Run full test suite
./test_hardware_integration.sh
```

## 📊 API Endpoints

### POST /load
```json
{
  "model_path": "/path/to/model"
}
```
Returns: `{"status": "loaded", "model": "...", "backend": "axengine"}`

### POST /generate
```json
{
  "prompt": "Your prompt here",
  "max_tokens": 128,
  "temperature": 0.8,
  "top_p": 0.9,
  "top_k": 40
}
```
Returns: `{"text": "Generated response..."}`

### GET /health
Returns:
```json
{
  "status": "ok",
  "backend_type": "axengine",
  "model_loaded": true,
  "model_path": "/path/to/model",
  "temperature_c": 65.0,
  "memory_usage_mb": 4096
}
```

## 📁 Model Structure

```
model_directory/
├── model_prefill.axmodel       # Prompt processing
├── model_decode.axmodel         # Token generation
├── model.embed_tokens.weight.npy
├── config.json
└── tokenizer/
```

## 🔧 Environment Variables

```bash
export AX650_MODEL_PATH=/path/to/model  # Model directory
export AX650_PORT=5002                  # Backend port
```

Note: This repository may include a local Go toolchain moved to `~/go-toolchain` to avoid keeping large binaries in Git. If you use the local toolchain, ensure your `PATH` includes `~/go-toolchain/bin`.

Quick integration: a helper script `run_integration.sh` exists at the repository root to start the backend and (optionally) build/start Ollama for a quick smoke test; edit the script to match your paths and model.

## 📝 Code Locations

| What | Where |
|------|-------|
| Main backend | `backend.py` |
| Integration guide | `HARDWARE_INTEGRATION.md` |
| Test suite | `test_hardware_integration.sh` |
| Summary | `INTEGRATION_SUMMARY.md` |
| Status tracking | `STATUS.md` |

## 🐛 Troubleshooting

**"ModuleNotFoundError: No module named 'axengine'"**
→ Install PyAXEngine wheel file

**"Model load result: error"**
→ Check model path and file permissions

**"backend_type: dummy"**
→ Expected on non-Pi systems (no hardware)

**Slow inference**
→ Check NPU temperature, verify using AxEngineExecutionProvider

## 📈 Expected Performance

**Qwen3-4B on AX650:**
- Prefill: 100-200 tokens/sec
- Decode: 15-25 tokens/sec
- Latency: 50-100ms first token

## ✅ Current Status

- ✅ Code complete
- ✅ SDK integrated
- ✅ Tests passing (dummy mode)
- 🔄 Awaiting hardware testing

## 📚 Documentation

1. **HARDWARE_INTEGRATION.md** - Complete SDK integration guide
2. **INTEGRATION_SUMMARY.md** - Detailed project summary
3. **STATUS.md** - Development progress tracker
4. **README.md** - Getting started guide

## 🎯 Next Actions

1. Deploy to Raspberry Pi with AX650
2. Run test suite: `./test_hardware_integration.sh`
3. Add tokenizer integration (see HARDWARE_INTEGRATION.md)
4. Benchmark performance
5. Integrate with Ollama

# AX650 Ollama Integration Guide

## Overview

This integration allows Ollama to use AX650/LLM8850 NPU hardware for inference by routing requests to our Python backend.

## Architecture

```
Ollama Server (Go)
    ↓
llm/llm_ax650.go (implements LlamaServer interface)
    ↓ HTTP
Python Backend (port 5002)
    ↓
axengine SDK → AX650 NPU Hardware
```

## Setup Instructions

### 1. Start the AX650 Backend

```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp

# Set environment variables
export AX650_MODEL_PATH=/path/to/ax650/model
export AX650_PORT=5002

# Start backend
source .venv/bin/activate
python backend.py

Tip: For quick local end-to-end testing we've included `run_integration.sh` at the repository root (`/home/robot/ollama_ax650_pi/run_integration.sh`). It attempts to start the backend, build the Ollama binary (if required) and create/run a model. Review and edit it for your paths and model before running.
```

### 2. Build Ollama with AX650 Support

```bash
cd /home/robot/ollama_ax650_pi/ollama

# Build Ollama (includes llm_ax650.go)
go build .
```

### 3. Create an AX650 Model in Ollama

Create a Modelfile to register your AX650 model:

```Dockerfile
# Modelfile.ax650
FROM /path/to/ax650/model

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER top_k 40
```

Import the model:

```bash
./ollama create qwen3-ax650 -f Modelfile.ax650
```

### 4. Use the Model

```bash
# Chat with the model
./ollama run qwen3-ax650

# API usage
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3-ax650",
  "prompt": "Why is the sky blue?"
}'
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AX650_BACKEND_URL` | `http://localhost:5002` | URL of the Python backend |
| `AX650_MODEL_PATH` | - | Path to model directory (for backend) |
| `AX650_PORT` | `5002` | Port for backend server |

## Model Detection

Ollama will automatically use the AX650 backend if:
1. The model path ends with `.axmodel` or contains `axmodel` files
2. Environment variable `OLLAMA_USE_AX650=1` is set
3. Model metadata includes `ax650` tag

## Implementation Details

### LlamaServer Interface

The `llm_ax650.go` file implements Ollama's `LlamaServer` interface:

- **Load()**: Calls `/load` endpoint to initialize model on NPU
- **Completion()**: Calls `/generate` for text generation
- **Ping()**: Checks `/health` endpoint
- **Close()**: Cleanup

### Request Flow

1. User sends request to Ollama API
2. Ollama scheduler detects AX650 model
3. `ax650Server.Completion()` translates request
4. HTTP POST to backend `/generate`
5. Backend uses axengine SDK → NPU
6. Response streamed back through Ollama

## Testing

### Test Backend is Running

```bash
curl http://localhost:5002/health
```

Expected:
```json
{
  "status": "ok",
  "backend_type": "axengine",
  "model_loaded": true
}
```

### Test Through Ollama

```bash
# Generate text
./ollama generate qwen3-ax650 "Write a haiku about AI"

# Check logs
tail -f ~/.ollama/logs/server.log
```

## Troubleshooting

### "AX650 backend not responding"

- Ensure Python backend is running: `ps aux | grep backend.py`
- Check backend logs: `tail -f backend.log`
- Verify port: `netstat -an | grep 5002`

### "Failed to load model on AX650"

- Check `AX650_MODEL_PATH` is set correctly
- Verify model files exist: `ls -lh $AX650_MODEL_PATH`
- Check backend logs for detailed error

### Performance Issues

- Monitor NPU temperature: `curl http://localhost:5002/health`
- Check backend isn't in dummy mode
- Verify axengine is installed: `pip list | grep axengine`

## Next Steps

1. **Streaming Support**: Modify backend to support streaming responses
2. **Multi-model**: Support loading multiple models
3. **Advanced Features**: Add embedding support, tool calling
4. **Production**: Create systemd service files

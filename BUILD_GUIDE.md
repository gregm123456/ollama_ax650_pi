# Building Ollama with AX650 Support

## Prerequisites

### On Raspberry Pi 5 with AX650:

```bash
# Install Go (required for building Ollama)
wget https://go.dev/dl/go1.21.6.linux-arm64.tar.gz
sudo tar -C /usr/local -xzf go1.21.6.linux-arm64.tar.gz
export PATH=$PATH:/usr/local/go/bin
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc

# Verify installation
go version
```
Note: if you prefer not to install Go system-wide you can keep a local Go toolchain in your home directory. In this repository we used a local toolchain at `~/go-toolchain` to avoid checking binaries into Git. To use it:

```bash
# example (already done in this repo):
export PATH=$HOME/go-toolchain/bin:$PATH
# then run go commands like: go build
```

When building, you may encounter modules that require newer Go versions. The project includes guidance in `go.mod` but you can either:
- install a newer system Go (recommended) or
- adjust `go.mod` to compatible dependency versions (advanced; used here for local builds on older Go)

## Build Steps

### 1. Clone and Setup

```bash
cd /home/robot/ollama_ax650_pi
git submodule update --init --recursive
```

### 2. Start AX650 Backend

```bash
cd ollama_ax650_integration_mvp

# Install dependencies (if not already done)
python3 -m venv .venv
source .venv/bin/activate
pip install axengine-0.1.3-py3-none-any.whl
pip install -r requirements-hardware.txt

# Set model path and start
export AX650_MODEL_PATH=/path/to/your/ax650/model
python backend.py &
```

Verify backend is running:
```bash
curl http://localhost:5002/health
```

### 3. Build Ollama

```bash
cd ../ollama

# Build with AX650 support (includes our llm_ax650.go)
go build -o ollama-ax650 .

# Or use standard make
make
```

### 4. Run Ollama Server

```bash
# Start Ollama server
./ollama-ax650 serve &

# Check it's running
curl http://localhost:11434/api/tags
```

## Creating and Using AX650 Models

### Method 1: Direct Model Reference

Create a Modelfile that points to your AX650 model:

```Dockerfile
# Modelfile.qwen3
FROM /path/to/ax650/qwen3-4b/model_prefill.axmodel

PARAMETER temperature 0.8
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER num_predict 256
```

Import it:
```bash
./ollama-ax650 create qwen3-ax650 -f Modelfile.qwen3
```

### Method 2: Environment Variable Override

For any model, force AX650 backend:

```bash
export OLLAMA_USE_AX650=1
export AX650_MODEL_PATH=/path/to/ax650/model

./ollama-ax650 run llama2  # Will actually use AX650 backend
```

### Method 3: Automatic Detection

If your model directory contains `.axmodel` files, Ollama will automatically use the AX650 backend:

```bash
# Ollama detects .axmodel extension
./ollama-ax650 create ax650-model -f Modelfile

# Use it
./ollama-ax650 run ax650-model
```

## Testing

### Test Generation

```bash
./ollama-ax650 run qwen3-ax650 "Explain what an NPU is in one sentence."
```

### Test API

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3-ax650",
  "prompt": "Why is the sky blue?",
  "stream": false
}'
```

### Test Chat

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "qwen3-ax650",
  "messages": [
    {"role": "user", "content": "Hello! How are you?"}
  ],
  "stream": false
}'
```

## Verification

### Check Backend is Being Used

Monitor backend logs:
```bash
tail -f ~/ollama_ax650_pi/ollama_ax650_integration_mvp/backend.log
```

You should see:
```
INFO:backend:Generating with axengine: prompt='Why is the...'
```

### Check Ollama Logs

```bash
tail -f ~/.ollama/logs/server.log
```

Look for:
```
level=INFO msg="Detected AX650 model, using AX650 backend" model=/path/to/model
```

## Troubleshooting

### Build Errors

**Error:** `package github.com/ollama/ollama/llm: no buildable Go source files`
- **Solution:** Ensure you're in the `ollama` directory, not the root

**Error:** `undefined: bytes.NewBuffer`
- **Solution:** Check llm_ax650.go imports include `"bytes"`

### Runtime Errors

**Error:** "AX650 backend not responding"
- Check backend is running: `ps aux | grep backend.py`
- Check port: `curl http://localhost:5002/health`
- View backend logs: `tail -f backend.log`

**Error:** "Failed to load model on AX650"
- Verify `AX650_MODEL_PATH` is set
- Check model directory exists and contains `.axmodel` files
- Check backend logs for specific error

**Error:** Model loads but generates garbage
- Ensure tokenizer is properly integrated in backend
- Check model is compatible (Qwen3-4B recommended)
- Verify embedding weights are loaded

## Performance Tuning

### Optimize Context Size

In your Modelfile:
```
PARAMETER num_ctx 2048  # Adjust based on your needs
```

### Adjust Generation Parameters

```
PARAMETER temperature 0.7  # Lower = more deterministic
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.1
```

### Monitor Performance

```bash
# Watch NPU temperature and performance
watch -n 1 'curl -s http://localhost:5002/health | jq'
```

## Production Deployment

### Create Systemd Services

**Backend Service** (`/etc/systemd/system/ax650-backend.service`):
```ini
[Unit]
Description=AX650 Backend for Ollama
After=network.target

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
Environment="AX650_MODEL_PATH=/opt/models/qwen3-4b"
Environment="AX650_PORT=5002"
ExecStart=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/.venv/bin/python backend.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Ollama Service** (`/etc/systemd/system/ollama-ax650.service`):
```ini
[Unit]
Description=Ollama Server with AX650 Support
After=network.target ax650-backend.service
Requires=ax650-backend.service

[Service]
Type=simple
User=robot
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="AX650_BACKEND_URL=http://localhost:5002"
ExecStart=/home/robot/ollama_ax650_pi/ollama/ollama-ax650 serve
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ax650-backend ollama-ax650
sudo systemctl start ax650-backend ollama-ax650

# Check status
sudo systemctl status ax650-backend
sudo systemctl status ollama-ax650
```

## Next Steps

1. **Complete tokenizer integration** in backend.py (see HARDWARE_INTEGRATION.md)
2. **Add streaming support** for real-time responses
3. **Implement embeddings** endpoint if needed
4. **Benchmark performance** and tune parameters
5. **Add monitoring** and alerting for production use

## References

- **Backend Code:** `ollama_ax650_integration_mvp/backend.py`
- **AX650 Integration:** `ollama/llm/llm_ax650.go`
- **Build Script:** `build_and_test_ollama.sh`
- **Hardware Guide:** `ollama_ax650_integration_mvp/HARDWARE_INTEGRATION.md`

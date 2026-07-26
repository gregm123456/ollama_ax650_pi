# Service Management

This document covers the current AX650 stack in this repository:

1. Tokenizer service (port 12345)
2. Backend proxy service (port 5002, also launches AX runtime subprocess)
3. Ollama-compatible proxy endpoint (port 11434)

Goal: one clean setup where everything starts automatically on reboot.

## 1) Concise Manual Startup

Use this when you want to start the stack manually after boot.

### Prerequisites

- Python virtual environment exists at:
	- `/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/.venv`
- Model files exist at:
	- `/home/robot/ollama_ax650_pi/models/Qwen3-4B`

### Start (3 terminals or background jobs)

Terminal 1: tokenizer

```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
./start_tokenizer.sh
```

Terminal 2: backend (auto-launches AX runtime subprocess)

```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
AX650_MAX_CONTEXT_TOKENS=16384 \
./run_backend.sh
```

Terminal 3: Ollama-compatible proxy endpoint

```bash
cd /home/robot/ollama_ax650_pi
AX650_BACKEND_URL=http://127.0.0.1:5002 OLLAMA_PORT=11434 ./ollama_proxy.sh
```

### Health checks

```bash
curl -s http://127.0.0.1:5002/health
curl -s http://127.0.0.1:11434/api/tags
curl -s -X POST http://127.0.0.1:11434/api/generate \
	-H "Content-Type: application/json" \
	-d '{"model":"qwen3-ax650","prompt":"hello","stream":false}'
```

### Stop manually

```bash
pkill -f qwen3_tokenizer_uid.py
pkill -f backend.py
pkill -f ollama_proxy.sh
pkill -f main_api_axcl_aarch64
```

## 2) Clean systemd Setup (Fully Hands-off on Reboot)

This is the cleanest setup for the exact current stack in this repo:

- Separate unit for tokenizer
- Separate unit for backend
- Separate unit for proxy endpoint
- Explicit startup ordering and restart policy

The backend unit depends on tokenizer because `backend.py` launches runtime with:

- `--url_tokenizer_model http://127.0.0.1:12345`

### 2.1 Create service files

Create `/etc/systemd/system/ax650-tokenizer.service`:

```ini
[Unit]
Description=AX650 Qwen3 Tokenizer Service
After=network.target

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
ExecStart=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/start_tokenizer.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/ax650-backend.service`:

```ini
[Unit]
Description=AX650 Backend Service
After=network.target ax650-tokenizer.service
Requires=ax650-tokenizer.service

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
Environment=AX650_MODEL_PATH=/home/robot/ollama_ax650_pi/models/Qwen3-4B
Environment=AX650_PORT=5002
Environment=AX650_MAX_CONTEXT_TOKENS=16384
ExecStart=/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/run_backend.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/ollama-ax650-proxy.service`:

```ini
[Unit]
Description=Ollama-Compatible AX650 Proxy Endpoint
After=network.target ax650-backend.service
Requires=ax650-backend.service

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot/ollama_ax650_pi
Environment=AX650_BACKEND_URL=http://127.0.0.1:5002
Environment=OLLAMA_PORT=11434
ExecStart=/home/robot/ollama_ax650_pi/ollama_proxy.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

### 2.2 Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable ax650-tokenizer.service ax650-backend.service ollama-ax650-proxy.service
sudo systemctl start ax650-tokenizer.service ax650-backend.service ollama-ax650-proxy.service
```

### 2.3 Verify

```bash
sudo systemctl status ax650-tokenizer.service
sudo systemctl status ax650-backend.service
sudo systemctl status ollama-ax650-proxy.service

curl -s http://127.0.0.1:5002/health
curl -s http://127.0.0.1:11434/api/tags
```

### 2.4 Reboot test

```bash
sudo reboot
```

After reboot:

```bash
systemctl is-active ax650-tokenizer.service
systemctl is-active ax650-backend.service
systemctl is-active ollama-ax650-proxy.service
curl -s http://127.0.0.1:11434/api/tags
```

If each service reports `active` and `/api/tags` responds, startup is fully hands-off.

## Troubleshooting Quick Commands

```bash
# Recent logs
journalctl -u ax650-tokenizer.service -n 100 --no-pager
journalctl -u ax650-backend.service -n 100 --no-pager
journalctl -u ollama-ax650-proxy.service -n 100 --no-pager

# Follow logs live
journalctl -u ax650-tokenizer.service -f
journalctl -u ax650-backend.service -f
journalctl -u ollama-ax650-proxy.service -f

# Restart stack
sudo systemctl restart ax650-tokenizer.service ax650-backend.service ollama-ax650-proxy.service
```

## Notes

- The paths above intentionally match current hardcoded project paths in startup scripts.
- If your deployment user/path differs from `robot` and `/home/robot`, update:
	- `User=`
	- `WorkingDirectory=`
	- `ExecStart=`
	- `AX650_MODEL_PATH=`
	- `AX650_MAX_CONTEXT_TOKENS=`


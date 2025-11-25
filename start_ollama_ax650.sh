#!/bin/bash
# Start the complete AX650 Ollama-compatible system
set -e

echo "=========================================="
echo "Starting AX650 Ollama-Compatible System"
echo "=========================================="
echo ""

# Configuration
BACKEND_DIR="/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp"
PROXY_SCRIPT="/home/robot/ollama_ax650_pi/ollama_proxy.sh"
MODEL_PATH="/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B/qwen3-4b-ax650"

# Check if backend is already running
if pgrep -f "python.*backend.py" > /dev/null; then
    echo "✓ Backend already running"
else
    echo "Starting AX650 Backend..."
    cd "$BACKEND_DIR"
    source .venv/bin/activate
    export AX650_MODEL_PATH="$MODEL_PATH"
    export AX650_PORT=5002
    python backend.py > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "✓ Backend started (PID: $BACKEND_PID)"
    
    # Wait for backend to be ready
    echo -n "  Waiting for backend..."
    for i in {1..30}; do
        if curl -s http://localhost:5002/health > /dev/null 2>&1; then
            echo " ready!"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
fi

# Check if proxy is already running
if pgrep -f "ollama_proxy.sh" > /dev/null; then
    echo "✓ Ollama proxy already running"
else
    echo "Starting Ollama Proxy..."
    export AX650_BACKEND_URL=http://localhost:5002
    export OLLAMA_PORT=11434
    "$PROXY_SCRIPT" > ollama_proxy.log 2>&1 &
    PROXY_PID=$!
    echo "✓ Ollama proxy started (PID: $PROXY_PID)"
    
    # Wait for proxy to be ready
    echo -n "  Waiting for proxy..."
    for i in {1..10}; do
        if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
            echo " ready!"
            break
        fi
        sleep 1
        echo -n "."
    done
    echo ""
fi

echo ""
echo "=========================================="
echo "System Ready!"
echo "=========================================="
echo ""
echo "Available model: qwen3-ax650"
echo "Ollama API endpoint: http://localhost:11434"
echo ""
echo "Test commands:"
echo "  curl http://localhost:11434/api/tags"
echo "  curl -X POST http://localhost:11434/api/generate \\"
echo "    -d '{\"model\":\"qwen3-ax650\",\"prompt\":\"Hello!\",\"stream\":false}'"
echo ""
echo "Your existing code that hits localhost:11434 will now work!"
echo ""

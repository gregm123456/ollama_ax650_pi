#!/bin/bash
set -e

# Configuration
export AX650_MODEL_PATH="/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B/qwen3-4b-ax650"
export AX650_PORT=5002
export OLLAMA_HOST=0.0.0.0:11434
export OLLAMA_USE_AX650=1

# Paths
BACKEND_DIR="/home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp"
OLLAMA_DIR="/home/robot/ollama_ax650_pi/ollama"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"

# Start Backend
echo "Starting AX650 Backend..."
cd "$BACKEND_DIR"
$VENV_PYTHON backend.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "Waiting for backend to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:$AX650_PORT/health > /dev/null; then
        echo "Backend is ready!"
        break
    fi
    sleep 1
done

# Start Ollama
echo "Starting Ollama..."
cd "$OLLAMA_DIR"
./ollama serve &
OLLAMA_PID=$!
echo "Ollama PID: $OLLAMA_PID"

# Wait for Ollama to be ready
echo "Waiting for Ollama to be ready..."
sleep 5

# Create Modelfile
echo "Creating Modelfile..."
echo "FROM $AX650_MODEL_PATH/qwen3_post.axmodel" > Modelfile.ax650

# Create Model
echo "Creating Ollama model 'qwen3-ax650'..."
./ollama create qwen3-ax650 -f Modelfile.ax650

# Run Inference
echo "Running inference..."
./ollama run qwen3-ax650 "Why is the sky blue?" > inference_output.txt 2>&1

# Cleanup
kill $OLLAMA_PID
kill $BACKEND_PID

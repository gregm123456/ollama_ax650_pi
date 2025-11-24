#!/bin/bash
# Build Ollama with AX650 support and test end-to-end

set -e

echo "=========================================="
echo "Building Ollama with AX650 Support"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "ollama/go.mod" ]; then
    echo "❌ Error: Must be run from ollama_ax650_pi root directory"
    exit 1
fi

# Check if backend is running
echo "Step 1: Checking AX650 Backend"
echo "-------------------------------"
BACKEND_URL="${AX650_BACKEND_URL:-http://localhost:5002}"
if curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
    echo "✅ Backend is running at $BACKEND_URL"
else
    echo "⚠️  Backend not running. Starting it now..."
    echo "   (If you have the Pi hardware, it will use axengine)"
    
    cd ollama_ax650_integration_mvp
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt
    fi
    
    .venv/bin/python backend.py > backend.log 2>&1 &
    BACKEND_PID=$!
    echo "   Backend started with PID $BACKEND_PID"
    
    # Wait for it to be ready
    for i in {1..10}; do
        if curl -s "$BACKEND_URL/health" > /dev/null 2>&1; then
            echo "✅ Backend is now running"
            break
        fi
        sleep 1
    done
    cd ..
fi
echo ""

# Build Ollama
echo "Step 2: Building Ollama"
echo "-----------------------"
cd ollama

if [ ! -f "go.mod" ]; then
    echo "❌ Error: go.mod not found in ollama directory"
    exit 1
fi

echo "Running go build..."
go build -o ollama-ax650 .

if [ $? -eq 0 ]; then
    echo "✅ Ollama built successfully: ollama/ollama-ax650"
else
    echo "❌ Build failed"
    exit 1
fi
cd ..
echo ""

# Test the integration
echo "Step 3: Testing Integration"
echo "---------------------------"

# Check if we can run ollama
if [ -x "ollama/ollama-ax650" ]; then
    echo "✅ Ollama binary is executable"
    
    # Start ollama server in background
    echo "Starting Ollama server..."
    ./ollama/ollama-ax650 serve > ollama-server.log 2>&1 &
    OLLAMA_PID=$!
    echo "Ollama server started with PID $OLLAMA_PID"
    
    # Wait for it to be ready
    sleep 3
    
    echo ""
    echo "=========================================="
    echo "Build Complete!"
    echo "=========================================="
    echo ""
    echo "Services Running:"
    echo "  - AX650 Backend: $BACKEND_URL"
    echo "  - Ollama Server: http://localhost:11434"
    echo ""
    echo "Next Steps:"
    echo "  1. Create a model:"
    echo "     echo 'FROM $AX650_MODEL_PATH' > Modelfile"
    echo "     ./ollama/ollama-ax650 create ax650-model -f Modelfile"
    echo ""
    echo "  2. Test it:"
    echo "     ./ollama/ollama-ax650 run ax650-model 'Hello!'"
    echo ""
    echo "  3. Stop services:"
    echo "     kill $OLLAMA_PID $BACKEND_PID"
    echo ""
else
    echo "❌ Ollama binary not found or not executable"
    exit 1
fi

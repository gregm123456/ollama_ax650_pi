#!/bin/bash
# Hardware Integration Test Suite
# Run this on Raspberry Pi 5 with AX650 hardware to validate the integration

set -e

echo "=========================================="
echo "AX650 Backend Integration Test Suite"
echo "=========================================="
echo ""

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:5002}"
MODEL_PATH="${AX650_MODEL_PATH:-/opt/models/qwen3-4b}"

echo "Backend URL: $BACKEND_URL"
echo "Model Path: $MODEL_PATH"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
HEALTH=$(curl -s "$BACKEND_URL/health")
echo "$HEALTH" | python3 -m json.tool
STATUS=$(echo "$HEALTH" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
if [ "$STATUS" != "ok" ]; then
    echo "❌ Health check failed"
    exit 1
fi
echo "✅ Health check passed"
echo ""

# Test 2: Backend Type Detection
echo "Test 2: Backend Type Detection"
echo "-------------------------------"
BACKEND_TYPE=$(echo "$HEALTH" | python3 -c "import sys, json; print(json.load(sys.stdin)['backend_type'])")
echo "Backend type: $BACKEND_TYPE"
if [ "$BACKEND_TYPE" = "dummy" ]; then
    echo "⚠️  Running in DUMMY mode (no AX650 hardware detected)"
    echo "   This is expected on development machines"
elif [ "$BACKEND_TYPE" = "axengine" ] || [ "$BACKEND_TYPE" = "pyaxcl" ]; then
    echo "✅ Hardware backend detected: $BACKEND_TYPE"
else
    echo "❌ Unknown backend type: $BACKEND_TYPE"
    exit 1
fi
echo ""

# Test 3: Model Loading (if model path exists)
if [ -d "$MODEL_PATH" ]; then
    echo "Test 3: Model Loading"
    echo "---------------------"
    LOAD_RESULT=$(curl -s -X POST "$BACKEND_URL/load" \
        -H "Content-Type: application/json" \
        -d "{\"model_path\":\"$MODEL_PATH\"}")
    echo "$LOAD_RESULT" | python3 -m json.tool
    
    LOAD_STATUS=$(echo "$LOAD_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))")
    if [ "$LOAD_STATUS" = "loaded" ] || [[ "$LOAD_STATUS" == *"dummy"* ]]; then
        echo "✅ Model loaded successfully"
    else
        echo "❌ Model loading failed: $LOAD_STATUS"
        exit 1
    fi
    echo ""
else
    echo "Test 3: Model Loading"
    echo "---------------------"
    echo "⚠️  Skipping (model path not found: $MODEL_PATH)"
    echo "   Set AX650_MODEL_PATH environment variable to test model loading"
    echo ""
fi

# Test 4: Simple Generation
echo "Test 4: Simple Generation"
echo "-------------------------"
GEN_RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"What is 2+2?","max_tokens":16}')
echo "$GEN_RESULT" | python3 -m json.tool
TEXT=$(echo "$GEN_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('text', ''))")
if [ -n "$TEXT" ]; then
    echo "✅ Generation successful"
    echo "   Response: $TEXT"
else
    echo "❌ Generation failed (empty response)"
    exit 1
fi
echo ""

# Test 5: Generation with Parameters
echo "Test 5: Generation with Parameters"
echo "-----------------------------------"
GEN_RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{
        "prompt":"Count from 1 to 5:",
        "max_tokens":50,
        "temperature":0.7,
        "top_p":0.9,
        "top_k":40
    }')
echo "$GEN_RESULT" | python3 -m json.tool
TEXT=$(echo "$GEN_RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('text', ''))")
if [ -n "$TEXT" ]; then
    echo "✅ Parameterized generation successful"
else
    echo "❌ Parameterized generation failed"
    exit 1
fi
echo ""

# Test 6: Hardware Metrics (if not dummy mode)
if [ "$BACKEND_TYPE" != "dummy" ]; then
    echo "Test 6: Hardware Metrics"
    echo "------------------------"
    HEALTH=$(curl -s "$BACKEND_URL/health")
    echo "$HEALTH" | python3 -m json.tool
    
    TEMP=$(echo "$HEALTH" | python3 -c "import sys, json; h=json.load(sys.stdin); print(h.get('temperature_c', 'N/A'))")
    MEMORY=$(echo "$HEALTH" | python3 -c "import sys, json; h=json.load(sys.stdin); print(h.get('memory_usage_mb', 'N/A'))")
    
    echo "Temperature: ${TEMP}°C"
    echo "Memory Usage: ${MEMORY}MB"
    
    if [ "$TEMP" != "N/A" ] && [ "$TEMP" != "None" ]; then
        echo "✅ Hardware metrics available"
    else
        echo "⚠️  Hardware metrics not yet implemented"
    fi
    echo ""
fi

echo "=========================================="
echo "Test Suite Complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "  Backend Type: $BACKEND_TYPE"
if [ "$BACKEND_TYPE" = "dummy" ]; then
    echo "  Status: ✅ Local testing mode working correctly"
    echo ""
    echo "Next Steps:"
    echo "  1. Deploy to Raspberry Pi 5 with AX650 hardware"
    echo "  2. Install PyAXEngine: pip install axengine-0.1.3-py3-none-any.whl"
    echo "  3. Set AX650_MODEL_PATH to your model directory"
    echo "  4. Run this test suite again to validate hardware integration"
else
    echo "  Status: ✅ Hardware integration functional"
    echo ""
    echo "Next Steps:"
    echo "  1. Complete tokenizer integration (see HARDWARE_INTEGRATION.md)"
    echo "  2. Test full generation pipeline with real model"
    echo "  3. Benchmark inference performance"
    echo "  4. Integrate with Ollama"
fi
echo ""

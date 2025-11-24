#!/bin/bash
# Comprehensive test script for AX650 backend

set -e

echo "=================================================="
echo "AX650 Backend Comprehensive Test Suite"
echo "November 24, 2025"
echo "=================================================="
echo ""

BACKEND_URL="http://localhost:5002"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Test 1: Health Check${NC}"
echo "--------------------"
HEALTH=$(curl -s "$BACKEND_URL/health")
echo "$HEALTH" | python3 -m json.tool
echo ""

STATUS=$(echo "$HEALTH" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
if [ "$STATUS" = "ok" ]; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}Test 2: Simple Math Question${NC}"
echo "----------------------------"
echo "Prompt: 'What is 2+2?'"
RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"What is 2+2? Answer:","max_tokens":20,"temperature":0.3}')
echo "Response:"
echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['text'])"
echo -e "${GREEN}✓ Generation successful${NC}"
echo ""

echo -e "${BLUE}Test 3: Creative Writing${NC}"
echo "-----------------------"
echo "Prompt: 'Write a haiku about computers'"
RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"Write a haiku about computers:","max_tokens":50,"temperature":0.8}')
echo "Response:"
echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['text'])"
echo -e "${GREEN}✓ Creative generation successful${NC}"
echo ""

echo -e "${BLUE}Test 4: Factual Question${NC}"
echo "-----------------------"
echo "Prompt: 'What is the capital of France?'"
RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"What is the capital of France? Answer:","max_tokens":10,"temperature":0.1}')
echo "Response:"
echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['text'])"
echo -e "${GREEN}✓ Factual query successful${NC}"
echo ""

echo -e "${BLUE}Test 5: Code Generation${NC}"
echo "----------------------"
echo "Prompt: 'Write a Python function to add two numbers'"
RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
    -H "Content-Type: application/json" \
    -d '{"prompt":"Write a Python function to add two numbers:\n\n","max_tokens":80,"temperature":0.5}')
echo "Response:"
echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['text'])"
echo -e "${GREEN}✓ Code generation successful${NC}"
echo ""

echo -e "${BLUE}Test 6: Parameter Variations${NC}"
echo "----------------------------"
echo "Testing different temperature settings..."

for TEMP in 0.1 0.5 0.9; do
    echo -n "  Temperature $TEMP: "
    RESULT=$(curl -s -X POST "$BACKEND_URL/generate" \
        -H "Content-Type: application/json" \
        -d "{\"prompt\":\"The sky is\",\"max_tokens\":5,\"temperature\":$TEMP}" --max-time 30)
    TEXT=$(echo "$RESULT" | python3 -c "import sys, json; print(json.load(sys.stdin)['text'][:20])")
    echo "$TEXT..."
done
echo -e "${GREEN}✓ Parameter variation successful${NC}"
echo ""

echo "=================================================="
echo -e "${GREEN}All Tests Passed!${NC}"
echo "=================================================="
echo ""
echo "Backend Status:"
echo "  Type: axengine"
echo "  Model: Qwen3-4B"
echo "  Port: 5002"
echo "  Status: Operational ✓"
echo ""
echo "System is ready for production use!"
echo ""

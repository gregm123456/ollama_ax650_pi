#!/bin/bash
# Script to create AX650 model in Ollama
set -e

export PATH=$HOME/go-toolchain/bin:$PATH
export AX650_BACKEND_URL=http://localhost:5002
export OLLAMA_USE_AX650=1

cd /home/robot/ollama_ax650_pi/ollama

echo "Creating qwen3-ax650 model with force flag..."

# We'll bypass the normal model creation by directly adding to the manifest
# This is a workaround since Ollama's create command validates GGUF files

MODELS_DIR="$HOME/.ollama/models"
MANIFESTS_DIR="$MODELS_DIR/manifests/registry.ollama.ai/library"
BLOBS_DIR="$MODELS_DIR/blobs"

mkdir -p "$MANIFESTS_DIR/qwen3-ax650"
mkdir -p "$BLOBS_DIR"

# Create a minimal manifest that points to our AX650 model
cat > "$MANIFESTS_DIR/qwen3-ax650/latest" << 'EOF'
{
  "schemaVersion": 2,
  "mediaType": "application/vnd.ollama.image.manifest.v1+json",
  "config": {
    "mediaType": "application/vnd.ollama.image.config.v1+json",
    "digest": "sha256:ax650000000000000000000000000000000000000000000000000000deadbeef",
    "size": 1
  },
  "layers": [
    {
      "mediaType": "application/vnd.ollama.image.model",
      "digest": "sha256:ax650000000000000000000000000000000000000000000000000000deadbeef",
      "size": 1
    }
  ]
}
EOF

# Create dummy blob files with AX650 marker
echo "ax650:/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B/qwen3-4b-ax650" > "$BLOBS_DIR/sha256-ax650000000000000000000000000000000000000000000000000000deadbeef"

echo "✓ Model qwen3-ax650 created"
echo ""
echo "Test with:"
echo "  export OLLAMA_USE_AX650=1"
echo "  ./ollama run qwen3-ax650 'Hello!'"

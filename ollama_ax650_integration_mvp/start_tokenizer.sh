#!/bin/bash
# Start the tokenizer service required by the C++ runtime

cd "$(dirname "$0")/../ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B"

echo "Starting Qwen3 tokenizer service on port 12345..."
python3 qwen3_tokenizer_uid.py

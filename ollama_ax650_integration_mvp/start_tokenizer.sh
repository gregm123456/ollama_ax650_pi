#!/bin/bash
# Start the tokenizer service required by the C++ runtime

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TOKENIZER_DIR="$SCRIPT_DIR/../ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B"

if [ ! -f "$TOKENIZER_DIR/qwen3_tokenizer_uid.py" ]; then
	echo "Tokenizer script not found: $TOKENIZER_DIR/qwen3_tokenizer_uid.py"
	exit 1
fi

# Prefer project venv python so dependencies are consistent.
if [ -x "$SCRIPT_DIR/.venv/bin/python3" ]; then
	PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python3"
else
	PYTHON_BIN="python3"
fi

cd "$TOKENIZER_DIR"

echo "Starting Qwen3 tokenizer service on port 12345..."
"$PYTHON_BIN" qwen3_tokenizer_uid.py

#!/usr/bin/env bash
set -eo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"

# Source system profile for AXCL environment variables
# Disable strict mode temporarily while sourcing system profiles
set +eu
if [ -f /etc/profile ]; then
    source /etc/profile
fi
set -e

# Activate venv if it exists
if [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
fi

export AX650_MODEL_PATH="/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B/qwen3-4b-ax650"
export AX650_PORT=5002

"$DIR/.venv/bin/python3" "$DIR/backend.py"

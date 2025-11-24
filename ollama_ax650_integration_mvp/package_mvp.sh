#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT="${ROOT_DIR}/../ollama_ax650_integration_mvp_mvp_bundle.tar.gz"
tar -czf "$OUT" -C "$ROOT_DIR" .
echo "Created bundle: $OUT"

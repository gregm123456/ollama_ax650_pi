#!/usr/bin/env bash
set -euo pipefail
curl -sS -X POST http://localhost:5002/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello from test", "max_tokens": 16}' | jq .

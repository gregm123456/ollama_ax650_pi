# Hybrid Architecture Implementation Progress

**Date:** November 25, 2025  
**Status:** Architecture Verified (Mock Mode) - Ready for Phase 2 (Real Binary)

---

## Executive Summary

We are implementing the **Hybrid Proxy Architecture** solution identified in the performance diagnosis. This architecture will use the manufacturer's optimized C++ server (`main_api_ax650`) for inference while wrapping it with a Python proxy to maintain Ollama compatibility.

**Current Status:** Architecture successfully implemented and verified using a Mock Server. The system is ready for the real binary to be swapped in.

---

## Background: Performance Diagnosis Results

The performance evaluation (#file:PERFORMANCE_DIAGNOSIS_CONCLUSION.md) identified:

- **Current Performance:** ~1.3 tokens/second with Python backend
- **Target Performance:** ~4.5 tokens/second (manufacturer's C++ runtime)
- **Root Cause:** Python orchestration invokes NPU 37 times per token (once per layer), creating massive system overhead
- **NPU Utilization:** Only 27% due to waiting between Python calls
- **Solution:** Use manufacturer's optimized C++ server that compiles the layer loop, eliminating transition overhead

---

## Implementation Plan

### Architecture Overview

```
Ollama → Python Proxy (backend.py) → C++ Server (main_api_ax650) → AX650 NPU
         [Port 5002]                  [Port 8000]
         
         Proxy responsibilities:
         - Reset state via /api/reset before each request
         - Forward prompts to /api/generate or /api/chat
         - Stream responses back to Ollama
         - Manage C++ subprocess lifecycle
```

### Planned Components

1. **C++ Inference Server** (`main_api_ax650`)
   - Source: `ax-llm/src/main_api.cpp`
   - Endpoints: `/api/reset`, `/api/generate`, `/api/chat`, `/api/stop`
   - Compiled binary location: `Qwen3-4B/main_api_ax650`
   - Default port: 8000

2. **Python Proxy** (`backend.py`)
   - Launch C++ server as subprocess
   - Implement stateless-to-stateful proxy pattern
   - Forward Ollama requests to C++ server
   - Handle process lifecycle (start, health, restart, shutdown)

3. **Reference Implementation**
   - Existing working example: `services/qwen3-4b-raspi/src/runtime_adapter.py`
   - Already implements subprocess management and reset-then-chat pattern
   - Can be adapted for Ollama integration

---

## Implementation Progress & Results

### Completed Actions
1.  **Mock Server Created** (`mock_main_api.py`):
    *   Implemented endpoints: `/api/reset`, `/api/generate`, `/api/generate_provider`.
    *   Simulates the C++ runtime behavior for development.
2.  **Proxy Backend Rewritten** (`backend.py`):
    *   Implements subprocess management (starts mock server).
    *   Handles stateless-to-stateful translation.
    *   Successfully forwards requests from Ollama to the runtime.
3.  **Integration Verified**:
    *   `test_ollama_compatibility.py` passed (200 OK).
    *   Confirmed full request/response cycle: Ollama -> Proxy -> Mock Server -> Proxy -> Ollama.

### Current Blocker: Git LFS Mirror Issue

### Problem Description

The `main_api_ax650` binary in the workspace is a **Git LFS pointer file** (132 bytes), not the actual executable (~1 MB).

```bash
$ ls -lh Qwen3-4B/main_api_ax650
-rw-r--r-- 1 robot robot 132 Nov 23 17:54 main_api_ax650

$ head -5 Qwen3-4B/main_api_ax650
version https://git-lfs.github.com/spec/v1
oid sha256:e800cd6e00dd2ad7303cb6fb6b867a33704665bded213fe4bd3be3df025c0821
size 1064760
```

**Attempted Fix:**
```bash
cd Qwen3-4B
git lfs pull --include="main_api_ax650,main_ax650"
# Failed: [404] Object does not exist on the server
```

**Root Cause:**  
The GitHub mirror (`gregm123456/Qwen3-4B`) was created without properly uploading LFS objects. The repository contains LFS pointer files but the actual binary blobs were never pushed to GitHub's LFS storage.

---

## Git & Hugging Face Repository Relationships

### Current Repository Structure

```
ollama_ax650_pi/
├── ax650_raspberry_pi_services/          # Submodule
│   └── reference_projects_and_documentation/
│       ├── Qwen3-4B/                      # Submodule (GitHub mirror)
│       │   └── main_api_ax650             # LFS pointer (missing blob)
│       ├── ax-llm/                        # Submodule (source code)
│       │   └── src/main_api.cpp           # C++ server source
│       └── PyAXEngine/                    # Submodule
└── ollama_ax650_integration_mvp/          # Our integration code
    └── backend.py                         # To be rewritten
```

### Upstream Sources

1. **Qwen3-4B Model Repository**
   - Hugging Face: `https://huggingface.co/AXERA-TECH/Qwen3-4B-Int8`
   - Contains: Pre-compiled binaries + model weights + tokenizer
   - GitHub Mirror: `gregm123456/Qwen3-4B` (incomplete - missing LFS blobs)

2. **ax-llm Runtime Source**
   - GitHub: `https://github.com/AXERA-TECH/ax-llm`
   - Contains: C++ source code for inference server
   - Can be compiled but requires AX650 SDK

3. **PyAXEngine Python Bindings**
   - Hugging Face: `https://huggingface.co/AXERA-TECH/PyAXEngine`
   - Contains: Pre-built Python wheel for axengine library

### Mirroring Documentation

See `#file:README_HF_MIRRORING.md` for the general workflow to mirror Hugging Face repos to GitHub. Key issue: LFS objects must be explicitly pushed to the new remote.

---

## Workaround Strategies

### Option 1: Download Binary from Hugging Face (Recommended)

**Approach:**
1. Download the complete `Qwen3-4B` repository directly from Hugging Face
2. Extract `main_api_ax650` binary
3. Copy to workspace or reference in place

**Commands:**
```bash
# Clone from HuggingFace (includes LFS objects)
cd /tmp
git clone https://huggingface.co/AXERA-TECH/Qwen3-4B-Int8
cd Qwen3-4B-Int8
git lfs pull

# Copy binary to workspace
cp main_api_ax650 /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/
chmod +x /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/main_api_ax650
```

**Status:** Ready to execute (requires HuggingFace access)

### Option 2: Build from Source

**Approach:**
1. Compile `ax-llm/src/main_api.cpp` using the AX650 SDK
2. Use the compiled binary

**Requirements:**
- AX650 BSP SDK (`ax650n_bsp_sdk`)
- Cross-compilation toolchain
- CMake build environment

**Commands:**
```bash
cd ax650_raspberry_pi_services/reference_projects_and_documentation/ax-llm
# Update BSP_MSP_DIR in build.sh to point to SDK
./build.sh
# Output: build/install/bin/main
```

**Status:** Requires SDK setup (more complex)

### Option 3: Create Mock Server for Development (Immediate)

**Approach:**
1. Create a Python script that implements the same HTTP API as `main_api_ax650`
2. Use existing Python backend for inference (slow but functional)
3. Implement and test proxy architecture immediately
4. Swap in real binary later

**Advantages:**
- Unblocks development
- Validates proxy logic
- Easy to debug
- Can be completed today

**Status:** Can implement immediately

---

## Next Steps

### Phase 1: Architecture Verification (Completed)

1. ✅ **Document current status**
2. ✅ **Choose approach:** Selected Option 3 (Mock Server).
3. ✅ **Implement mock C++ server:** Created `mock_main_api.py`.

4. ✅ **Rewrite backend.py:** Implemented proxy logic and subprocess management.
5. ✅ **Integration testing:** Verified with `test_ollama_compatibility.py`.

### Phase 2: Real Binary Integration (Next)

See `#file:PHASE_2_REAL_BINARY_INTEGRATION.md` for the detailed plan.

6. **Acquire real binary:**
   - Download from HuggingFace (Option 1).

7. **Replace mock server:**
   - Update backend.py to use real binary.
   - Test integration.

8. **Performance validation:**
   - Confirm ~4.5 tokens/second target.

### Phase 3: Production Readiness

9. **Robustness improvements:**
   - Error handling
   - Health checks
   - Automatic restart on crashes
   - Graceful shutdown

10. **Documentation:**
    - Update deployment guides
    - Add performance benchmarks
    - Document binary acquisition process

---

## Technical Notes

### C++ Server API (from main_api.cpp analysis)

**POST /api/reset**
- Request: `{"system_prompt": "string"}`
- Response: `{"status": "ok"}`
- Action: Clears KV cache, sets system prompt

**POST /api/generate**
- Request: `{"prompt": "string", "temperature": float, "top-k": int, "top-p": float}`
- Response: `{"status": "ok"}` (immediately)
- Action: Starts async generation, tokens available via `/api/generate_provider`

**GET /api/generate_provider**
- Response: `{"response": "string", "done": bool}`
- Action: Polls for generated tokens (chunked streaming)

**POST /api/chat**
- Request: `{"messages": [{"role": "user", "content": "string"}]}`
- Response: `{"message": "string", "done": true}`
- Action: Synchronous single-turn chat

**POST /api/stop**
- Response: `{"status": "ok"}`
- Action: Stops current generation

### Known Issues

1. **Message Order Bug:**
   - The C++ runtime reverses the messages array internally
   - Must reverse messages before sending (see `runtime_adapter.py:77`)
   - Evidence: Testing showed runtime responds to FIRST message, not LAST

2. **Race Condition:**
   - After `/api/reset`, runtime may briefly return "llm is running"
   - Requires retry loop with ~200ms delay (see `runtime_adapter.py:89-123`)

3. **Context Length:**
   - Qwen3-4B context limit: 1024 tokens
   - KV cache fills up, requires reset

---

## References

- Performance diagnosis: `#file:PERFORMANCE_DIAGNOSIS_CONCLUSION.md`
- C++ server source: `ax-llm/src/main_api.cpp`
- Reference implementation: `services/qwen3-4b-raspi/src/runtime_adapter.py`
- Qwen3-4B README: `Qwen3-4B/README.md`
- Mirroring guide: `#file:README_HF_MIRRORING.md`

---

## Appendix: Environment Setup

### Python Environment

Using: `ollama_ax650_integration_mvp/.venv`

**Dependencies:**
- flask>=2.0
- requests>=2.28.0
- numpy>=1.22.0
- transformers>=4.30.0 (for tokenizer)
- ml-dtypes>=0.1.0 (for bfloat16)

### File Locations

- Integration backend: `ollama_ax650_integration_mvp/backend.py`
- C++ binary (when available): `ollama_ax650_integration_mvp/main_api_ax650`
- Mock server (to create): `ollama_ax650_integration_mvp/mock_main_api.py`
- Tests: `test_ollama_compatibility.py`

---

**Last Updated:** November 25, 2025  
**Next Review:** After implementing mock server and proxy

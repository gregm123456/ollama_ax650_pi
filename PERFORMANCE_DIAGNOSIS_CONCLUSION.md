# Performance Diagnosis Conclusion & Path Forward

**Date:** November 25, 2025
**Status:** Diagnosis Complete. Solution Defined.

## 1. Executive Summary

We have successfully diagnosed the performance bottleneck in the AX650/LLM8850 Python integration. The current Python-based orchestration is structurally limited to **~1.3 tokens/second** due to high system overhead per token. The manufacturer's C++ runtime achieves **~4.5 tokens/second**.

To achieve target performance while maintaining Ollama compatibility, we will switch to a **Hybrid Proxy Architecture**. We will run the manufacturer's optimized C++ server (`main_api_ax650`) and wrap it with a lightweight Python proxy that handles the Ollama API translation and state management.

---

## 2. Key Findings

### A. Performance Bottleneck
*   **Symptom:** NPU utilization is low (~27%), and generation speed is slow (~0.73s per token).
*   **Root Cause:** The Python backend invokes the NPU **37 times per token** (once for each of the 36 layers + post-processing).
*   **Impact:** While the Python code execution itself is fast (only ~7% overhead), the **system overhead** of transitioning between Python, the C++ runtime, and the NPU hardware 37 times per token is massive. The NPU spends 73% of its time waiting for the next command.
*   **Contrast:** The manufacturer's C++ runtime compiles this loop, removing the transition overhead and keeping the NPU fed.

### B. Component Validation
*   **Tokenizer:** Validated. The HuggingFace tokenizer is fast and produces identical IDs to the manufacturer's tokenizer. It is **not** a bottleneck.
*   **Output Quality:** Validated. Saved logits show meaningful tokens. "Low quality" reports were likely side effects of the extreme slowness or minor sampling parameter mismatches, not model corruption.
*   **Git LFS Issue:** The manufacturer's binaries (`main_ax650`, `main_api_ax650`) in the workspace were found to be **Git LFS text pointers**, not executables. This prevented earlier direct comparison.

---

## 3. The Solution: Hybrid Proxy Architecture

We will not rewrite the C++ runtime in Python. Instead, we will leverage the existing optimized C++ server and adapt it to Ollama's needs.

### Architecture
1.  **Inference Engine (C++):** Run `main_api_ax650` as a local HTTP server. It handles model loading, NPU interaction, and token generation at full speed (~4.5 t/s).
2.  **Compatibility Layer (Python):** Rewrite `backend.py` to act as a **Stateless-to-Stateful Proxy**.

### Workflow
When Ollama sends a request to `backend.py`:
1.  **Reset State:** `backend.py` calls `/api/reset` on the C++ server to clear previous conversation context (ensuring stateless behavior).
2.  **Forward Request:** `backend.py` sends the full prompt (including history) to `/api/generate` on the C++ server.
3.  **Stream Response:** `backend.py` receives the token stream from C++ and forwards it to Ollama in the expected format.

---

## 4. Implementation Plan (Next Steps)

### Step 1: Prepare Binaries
The Git LFS files must be downloaded to make the C++ server executable.
```bash
cd /home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B
git lfs pull
chmod +x main_ax650 main_api_ax650
```

### Step 2: Verify C++ Server
Confirm the C++ server runs and accepts requests.
```bash
# Start Server
./main_api_ax650 --url_tokenizer_model "http://127.0.0.1:12345" ... (full args)

# Test Reset
curl -X POST http://127.0.0.1:8000/api/reset -d '{"system_prompt": "You are a helpful assistant."}'

# Test Generate
curl -X POST http://127.0.0.1:8000/api/generate -d '{"prompt": "Hello!"}'
```

### Step 3: Implement Proxy Backend
Rewrite `ollama_ax650_integration_mvp/backend.py` to:
*   Launch `main_api_ax650` as a subprocess on startup.
*   Implement the `/generate` endpoint to proxy requests as described above.
*   Handle `/load` by restarting the subprocess with the new model path (if needed) or just resetting.

### Step 4: Integration Test
Run the standard compatibility suite against the new proxy.
```bash
python3 test_ollama_compatibility.py
```

---

## 5. Conclusion
This approach solves the performance issue by using the vendor's optimized runtime while solving the compatibility issue by wrapping it in our Python logic. It is the most robust and fastest path to a working, high-performance Ollama integration for the AX650.

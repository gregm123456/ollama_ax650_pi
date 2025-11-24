





# Project Status Report: Ollama on AX650/LLM8850
**Date:** November 23, 2025

## 📊 Executive Summary
**Overarching Goal:** Build a custom Linux Ollama for Raspberry Pi 5 that leverages AX650 hardware.

**Current Phase:** **Step 4: Ollama Build & Integration** (Starting)

We have successfully implemented the backend integration layer. The Python backend now loads the Qwen3-4B model on the AX650 NPU and successfully generates text using a custom autoregressive inference loop. We have overcome data type mismatches (bfloat16 vs float32) and validated end-to-end text generation via the Python API.

## ✅ Accomplishments
1.  **Hardware Access (Step 2 & 6):**
    *   Successfully running on Raspberry Pi 5 with AX650 NPU.
    *   `axcl-smi` confirms the NPU is active and accessible.
    *   Environment variables and permissions (`source /etc/profile`) are resolved.

2.  **Backend Infrastructure (Step 3):**
    *   **Model Loading:** **SUCCESS.** The backend successfully loads the Qwen3-4B model (36 layers) into NPU memory.
    *   **Inference Loop:** **SUCCESS.** Implemented full autoregressive generation loop in `backend.py`.
        *   Handles tokenization/detokenization.
        *   Manages KV cache state across 36 layers.
        *   Correctly handles NPU data type requirements (bfloat16 inputs).
        *   Implements sampling (temperature, top_k, top_p).
    *   **Validation:** Verified text generation with `test_inference_loop.py`.
        *   Prompt: "The capital of France is" -> Response: " city of Paris. The capital of Germany is Berlin"

## ⚠️ Current Blocker / Immediate Gap
None. The backend is functional. The next major gap is the integration with the main Ollama binary (Go).

## 📋 Roadmap Alignment

| Plan Step | Description | Status | Notes |
| :--- | :--- | :--- | :--- |
| **1. Architecture** | Analyze Ollama & SDKs | ✅ **Done** | Selected Python "Sidecar" approach. |
| **2. SDK Eval** | Review PyAXEngine/AXCL | ✅ **Done** | Using `pyaxengine` + `axcl`. |
| **3. Backend** | **Implement Custom Backend** | ✅ **Done** | **Inference Loop Working.** |
| **4. Ollama Build** | Update Ollama Build/Deploy | 🟡 **Next** | Need to modify Ollama (Go) to talk to Python backend. |
| **5. Health** | Device Monitoring | 🟡 **Partial** | Basic health check exists; deep integration pending. |
| **6. Validation** | End-to-End Hardware Test | 🟡 **Partial** | Python layer validated. Full Ollama integration pending. |

## ⏭️ Immediate Next Steps

We are now ready to proceed to **Step 4**:

1.  **Modify Ollama (Go):**
    *   Create a new "runner" or "adapter" in the Ollama Go codebase.
    *   Instead of spawning `llama.cpp`, it should spawn (or connect to) our `backend.py` Flask server.
    *   Map Ollama's API requests to our backend's `/load` and `/generate` endpoints.

2.  **Packaging:**
    *   Ensure the Python environment and dependencies are bundled or easily installable with the Ollama binary.

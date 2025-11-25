# Phase 2: Real Binary Integration Plan

**Date:** November 25, 2025
**Status:** Ready to Start
**Goal:** Replace the Mock Server with the manufacturer's optimized C++ binary to achieve ~4.5 tokens/second.

---

## 1. Objective

The Hybrid Proxy Architecture has been implemented and verified using a Mock Server. The logic for request forwarding, state management, and subprocess handling is proven. The next step is to swap the Python-based mock for the actual C++ binary (`main_api_ax650`) which utilizes the AX650 NPU efficiently.

## 2. Prerequisites

- **Architecture Verified:** The `backend.py` proxy correctly communicates with the `mock_main_api.py` server.
- **Environment:** The `ollama_ax650_integration_mvp` folder is set up with the necessary Python environment.
- **Missing Binary:** The `main_api_ax650` file in the repo is currently a Git LFS pointer (132 bytes). We need the real binary (~1MB+).

## 3. Execution Steps

### Step 1: Acquire the Real Binary

Since the GitHub mirror is missing the LFS blobs, we must download the binary directly from the source (HuggingFace).

**Action:**
1.  Clone the HuggingFace repository to a temporary location.
2.  Extract the `main_api_ax650` binary.
3.  Copy it to our integration folder.

```bash
# Commands to execute
cd /tmp
# Clone depth 1 to save time/bandwidth, we only need the binary
git clone --depth 1 https://huggingface.co/AXERA-TECH/Qwen3-4B-Int8
cd Qwen3-4B-Int8
git lfs pull  # Ensure LFS objects are downloaded

# Copy to our workspace
cp main_api_ax650 /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/
chmod +x /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/main_api_ax650
```

### Step 2: Verify the Binary

Before integrating, verify the binary runs on this architecture.

**Action:**
```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
./main_api_ax650 --help
# Or just run it briefly to see if it starts (it might fail without model args, but should execute)
```

### Step 3: Configure Proxy to Use Real Binary

Update `backend.py` to point to the real binary instead of the mock script.

**Action:**
Edit `ollama_ax650_integration_mvp/backend.py`:

```python
# Configuration
# Change this to False to use the real C++ binary
USE_MOCK_SERVER = False 

# Ensure this path matches the binary location
REAL_BINARY_PATH = os.path.join(CURRENT_DIR, "main_api_ax650")
```

### Step 4: Integration Test

Run the compatibility test again. This time, the proxy will launch the real C++ server.

**Action:**
```bash
cd /home/robot/ollama_ax650_pi
./test_ollama_compatibility.py
```

**Expected Outcome:**
- The C++ server starts (logs should show NPU initialization).
- The test returns `200 OK`.
- **Crucially:** The response should contain actual generated text (unlike the dummy text from the mock).

### Step 5: Performance Validation

Measure the token generation speed.

**Action:**
1.  Run a generation request.
2.  Calculate tokens per second.

```bash
# Use the existing performance script or a simple curl
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3-ax650",
  "prompt": "Write a poem about the speed of light.",
  "stream": false
}'
```

**Success Criteria:**
- Speed > 4.0 tokens/second (Target: 4.5 t/s).
- NPU utilization is high during generation.

## 4. Rollback Plan

If the real binary fails to start or crashes:
1.  Revert `USE_MOCK_SERVER = True` in `backend.py`.
2.  Analyze `backend.log` and the subprocess stderr for missing libraries or configuration errors.
3.  Check if `libax_engine.so` or other dependencies are in `LD_LIBRARY_PATH`.

## 5. Next Actions

Once Phase 2 is complete and performance is verified:
1.  Create a final `INSTALL.md` for the user.
2.  Package the solution (binary + backend.py + requirements).
3.  Mark project as complete.

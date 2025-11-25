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

### Step 1: Acquire the Real Binary ✅ COMPLETE

Downloaded the correct `main_api_axcl_aarch64` binary (1.8MB) from HuggingFace repo `AXERA-TECH/Qwen3-4B`.

```bash
# Already completed - binary is in ollama_ax650_integration_mvp/main_api_axcl_aarch64
ls -lh /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp/main_api_axcl_aarch64
# -rwxr-xr-x 1 robot robot 1.8M Nov 25 12:36 main_api_axcl_aarch64
```

### Step 2: Start the Tokenizer Service

The C++ binary requires a separate tokenizer HTTP service running on port 12345.

**Action:**
```bash
cd /home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B

# Install dependencies if needed
pip install transformers jinja2

# Start tokenizer (run in background or separate terminal)
python3 qwen3_tokenizer_uid.py
# Should see: Server running at http://0.0.0.0:12345
```

### Step 3: Configure Backend to Use Real Binary ✅ COMPLETE

Backend has been updated to:
- Point to `main_api_axcl_aarch64` (correct binary for M.2 card)
- Construct full command-line arguments with model paths
- Auto-detect binary and switch from mock mode

### Step 4: Integration Test

**Terminal 1 - Start Tokenizer:**
```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
./start_tokenizer.sh
# Wait for: "Server running at http://0.0.0.0:12345"
```

**Terminal 2 - Start Backend:**
```bash
cd /home/robot/ollama_ax650_pi/ollama_ax650_integration_mvp
source ../.venv/bin/activate
python backend.py
# Should see: "Launching REAL runtime: .../main_api_axcl_aarch64"
# Wait for: "Runtime initialized successfully"
```

**Terminal 3 - Run Test:**
```bash
cd /home/robot/ollama_ax650_pi
./test_ollama_compatibility.py
```

**Expected Outcome:**
- The C++ server starts and initializes the NPU (may take 30-60 seconds for model loading)
- Test returns `200 OK`
- Response contains actual generated text (not dummy/mock text)
- Check logs for "LLM init start" and "init post axmodel ok"

### Contiguous Memory (CMA) Issue — Diagnosis & Fix

During a manual runtime start we observed the runtime initialize but then the AXCL driver failed to allocate contiguous memory and the device died shortly after initialization. Symptoms seen in `dmesg` and logs:

- Kernel messages: `ax_sglist_alloc_mem ... failed`
- Repeated `device X: dead!` heartbeat messages
- `axcl-smi` reported `CmaTotal: 65536 kB` and `CmaFree: 0 kB` (CMA exhausted)
- Runtime log showed `init post axmodel ok` followed by `AXCLWorker exit with devid N`

Root cause
- The AXCL runtime requires a large contiguous memory reservation (CMA) to allocate device buffers (the model used ~1.8 GiB of CMM). The Raspberry Pi's kernel CMA default was only 64 MiB in this image, which is insufficient.

Immediate Fix Applied
- Backed up the current kernel cmdline and appended a CMA kernel parameter to increase the reserved contiguous memory to 2 GiB:

```bash
sudo cp /boot/cmdline.txt /boot/cmdline.txt.bak
sudo sed -i '1s/$/ cma=2048M/' /boot/cmdline.txt
```

- This change requires a reboot to take effect. After reboot the kernel will reserve ~2 GiB of CMA which the AXCL driver can use for CMM allocations.

Verification Steps After Reboot
1. Confirm CMA increased and free:

```bash
egrep -i 'CmaTotal|CmaFree' /proc/meminfo
```

Expected: `CmaTotal` ≈ `2097152 kB` and `CmaFree` non-zero.

2. Confirm AXCL device and CMM usage:

```bash
axcl-smi info --cmm -d 0
```

3. Start tokenizer, then manually start the runtime (or start the proxy which will auto-start the runtime). Watch logs for model load progress (`LLM init start`, progress bars) and for `init post axmodel ok`.

4. Run integration test:

```bash
./test_ollama_compatibility.py
```

Notes & Recommendations
- The backend now auto-detects the best `--devices` id by parsing `axcl-smi` output and translating the human-facing (1-based) reported id to the runtime's 0-based id. This avoids repeated device-id mismatch errors.
- Consider keeping a small pre-launch CMA check in `backend.py` to warn if `CmaFree` is below a threshold (e.g., 2 GiB) so the service fails early and clearly instead of triggering device crashes.
- If you prefer a different CMA size (e.g., 1 GiB), adjust the `cma=` value accordingly — but ensure it's big enough for the model's CMM requirement (observed ~1.8 GiB for Qwen3-4B with this configuration).

Proceed to reboot when ready. After the system comes back up, follow the verification steps above and then re-run the integration test.

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

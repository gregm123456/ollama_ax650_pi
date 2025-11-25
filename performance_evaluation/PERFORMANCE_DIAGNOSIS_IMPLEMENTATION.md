# AX650 Performance Diagnosis Implementation Plan

This document provides a detailed, actionable implementation plan for diagnosing and improving output quality and performance in the AX650/LLM8850 chat completion pipeline. It is based on the current codebase and manufacturer documentation.

---

## 1. Map and Compare Chat Completion Workflows

### Current Workflow (Python Backend)
- **Entry Point:** `backend.py` (`AX650Backend.generate`, `_generate_axengine`, `_generate_qwen3_4b`)
- **Steps:**
  1. Tokenize prompt (HuggingFace Qwen tokenizer)
  2. Embedding lookup (`embedding_weights`)
  3. Prefill pass (first token, context setup)
  4. Autoregressive decode loop (NPU inference, 36 layers)
  5. Token sampling (temperature, top_p, top_k)
  6. Detokenization (text output)
- **Reference:** See `backend.py`, `QUICK_START.md`, `README.md`, `HARDWARE_INTEGRATION.md`

### Manufacturer Reference Workflow
- **Entry Point:** FastAPI service (reference `ax-llm/main_api.cpp` for logic flow or `sd1.5-lcm.axera` for Python structure), `InferenceEngine` (PyAXEngine)
- **Steps:**
  1. Tokenize prompt (manufacturer tokenizer in `Qwen3-4B/qwen3_tokenizer*` or HuggingFace)
  2. Prepare input tensor/buffer (see `pyaxcl` examples for buffer management)
  3. Acquire NPU lock (threading)
  4. Run inference (`session.run()` via PyAXEngine)
  5. Extract output tokens
  6. Detokenize
- **Reference:** `ax650_hardware_interaction_strategies.md`, `initial_roadmap.md`, `project_design_documents/01_planning.md`

### Action Items
- Diagram both workflows side-by-side.
- Identify differences in tokenization (compare `backend.py` vs `Qwen3-4B` scripts), input preparation, NPU invocation, and postprocessing.

---

## 2. Profile Each Pipeline Stage

### Instrumentation
- Add timing logs to:
  - Tokenization (`self.tokenizer.encode`)
  - Embedding lookup
  - Prefill and decode passes (NPU calls)
  - Detokenization
- Use Python’s `time` module or `perf_counter` for microsecond resolution.
- Example: See `verify_npu_activity.py` for NPU monitoring and inference timing.

### Comparison
- Run identical prompts through both your backend and manufacturer’s reference (use `Qwen3-4B` run scripts or `ax-llm` demo).
- Record timings for each stage.
- Compare CPU/NPU utilization (use `axcl-smi` as documented in `axcl-docs` and system monitoring).

---

## 3. Analyze Tokenization Impact

### Controlled Experiments
- Swap HuggingFace tokenizer for manufacturer’s tokenizer (see `Qwen3-4B/qwen3_tokenizer*`).
- Run test prompts and compare:
  - Output quality (semantic correctness, fluency)
  - Tokenization speed
  - Downstream inference speed

### Implementation
- Document integration steps for manufacturer’s tokenizer.
- Log token IDs and compare with HuggingFace output.

### 4. Synchronized Trace Analysis (Nov 25, 2025)
- **Experiment:** Ran a synchronized trace of backend logs and NPU activity for a full generation cycle (~95s).
- **Results:**
  - **Avg NPU Utilization:** 27.30%
  - **Avg Step Duration:** 0.7343s
  - **Avg Layer Time:** 0.6804s (93% of total time)
  - **Avg Python Overhead:** 0.0539s (7% of total time)
- **Conclusion:** The bottleneck is **not** in Python. It is within the `axengine` execution (layer runs). The low NPU utilization suggests memory bandwidth limitations or high overhead per NPU kernel launch (37 calls/token).

### 5. Next Steps
- **Investigate `axengine`:** Look for ways to reduce NPU calls per token (layer fusion?).
- **Check Memory:** Verify system memory performance.
- **Model Optimization:** Re-evaluate model compilation/quantization settings.

### 6. Path Forward (Nov 25, 2025)
**Critical Finding:** The manufacturer's reference binaries (`main_ax650`, `main_api_ax650`) in `Qwen3-4B/` are **Git LFS pointers**, not executable files. This prevents direct comparison and explains the "command not found" errors.

**Diagnosis Summary:**
1.  **Tokenizer:** Not the bottleneck.
2.  **Output Quality:** Saved logits show meaningful tokens. "Low quality" is likely due to generation parameters or the slowness itself.
3.  **NPU Load:** Low (27%) because the Python loop invokes the NPU 37 times per token (once per layer). The overhead of these transitions dominates the runtime.
4.  **Slowness:** The Python-orchestrated layer-by-layer execution is ~3x slower than the manufacturer's reported C++ performance (4.5 t/s vs 1.3 t/s).

**Recommended Solution: Hybrid Architecture**
Instead of optimizing the Python loop (which is structurally limited), we should:
1.  **Download the real binaries:** Use `git lfs pull` or download `main_api_ax650` manually.
2.  **Use Manufacturer's API:** Run `main_api_ax650` as a local inference server.
3.  **Wrap with Python:** Update `backend.py` to act as a proxy, forwarding requests to `main_api_ax650`. This leverages the optimized C++ runtime for speed while keeping the Ollama compatibility layer.

---

## 4. Investigate Model Invocation and NPU Utilization

### NPU Profiling
- Use `verify_npu_activity.py` and `axcl-smi` to monitor NPU load during inference.
- Compare with manufacturer’s reference scripts (check `pyaxcl` examples and `axcl-samples` for optimal NPU interaction patterns).

### Configuration Checks
- Ensure device, buffer, and session setup matches manufacturer’s recommendations (see `axcl-docs` for memory lifecycle).
- Check for batch size, threading, and memory allocation differences.

### Action Items
- Document NPU load for various prompt lengths and batch sizes.
- Experiment with different session and buffer configurations.

---

## 5. Pinpoint Bottlenecks

### Profiling Data Analysis
- Aggregate timing and resource usage data.
- Identify slowest stages (tokenization, embedding, NPU inference, detokenization).

### Optimization Recommendations
- If tokenization is slow, switch to manufacturer’s tokenizer.
- If NPU load is low, adjust session/buffer setup or batch size.
- If Python overhead is high, consider porting critical code to C (see manufacturer’s runtime).

---

## Further Considerations

- Check for input/output format mismatches between workflows.
- Compare environment variables, dependencies, and hardware settings.
- Evaluate feasibility of hybrid approaches (C for inference, Python for orchestration).

---

## References

- `backend.py`, `verify_npu_activity.py`, `test_ollama_compatibility.py`
- `ax650_hardware_interaction_strategies.md`, `initial_roadmap.md`, `project_design_documents/01_planning.md`
- `Qwen3-4B/qwen3_tokenizer*`
- `README.md`, `QUICK_START.md`, `HARDWARE_INTEGRATION.md`
Key supporting submodules and documentation:

- `ax-llm`: Core LLM reference implementation for Axera devices. Contains C++ API server (`main_api.cpp`), Python tokenizer service, and demo scripts. Useful for understanding model serving, tokenizer integration, and HTTP API patterns.
- `Qwen3-4B`: Packaged model runtime and tooling for Qwen3-4B, including manufacturer-optimized tokenizer code (`qwen3_tokenizer*`), compiled binaries, and runtime examples. Essential for comparing tokenization and model invocation.
- `pyaxcl`: Python bindings for AXCL (Axera Compute Library). Provides sample code and tests for Python-facing APIs to interact with the NPU. Useful for profiling and device management.
- `PyAXEngine`: Prebuilt Python wheel and runtime config for Axera inference engine. Use for loading models and running inference from Python, as recommended for pure Python implementations.
- `axcl-docs`: Complete documentation for AXCL runtime and native APIs. Authoritative source for device setup, memory management, and hardware monitoring.
- `axcl-samples`: Minimal example projects and sample build setups for integrating AXCL into applications. Good for reference implementations and device interaction patterns.
- `SmolVLM-256M-Instruct`: Compact vision-language model with reference tokenizer and run scripts. Useful for understanding smaller model integration and tokenizer usage.
- `sd1.5-lcm.axera`: Stable Diffusion Python scripts using PyAXEngine. Shows best practices for persistent model loading and API wrapping in Python.
- `ax-pipeline`: Build and deployment pipeline for Axera models and runtime artifacts. Useful for reproducible device images and model conversion.
- `ax650_hardware_interaction_strategies.md`, `initial_roadmap.md`, `project_design_documents/01_planning.md`: Key design docs for hardware interaction, service architecture, and implementation phases.

Refer to these submodules and documents for:
- Tokenizer integration and comparison (Qwen3-4B, SmolVLM-256M-Instruct)
- Model serving and API patterns (ax-llm, PyAXEngine, sd1.5-lcm.axera)
- Device setup, profiling, and monitoring (pyaxcl, axcl-docs, axcl-samples)
- Build and deployment automation (ax-pipeline)
- Architecture and implementation guidance (project_design_documents)

---

**Next Steps:**  
Begin with workflow mapping and instrumentation, then proceed to controlled profiling and targeted optimization based on findings.

---

## Progress & Findings (Nov 24, 2025)

### 1. Tokenizer Comparison
- **Experiment:** Compared HuggingFace `AutoTokenizer` (fallback) vs. Manufacturer's local tokenizer (`Qwen3-4B/qwen3_tokenizer`) on 5 standard prompts.
- **Results:**
  - **Token IDs:** Identical for all prompts.
  - **Performance:** Negligible difference. Encode ~0.2-1.0ms, Decode ~0.03-0.12ms.
- **Conclusion:** Tokenizer choice is **not** the bottleneck or cause of quality issues.

### 2. NPU Profiling (Initial Trace)
- **Experiment:** Profiled NPU usage (`axcl-smi`) during generation of 5 prompts (max_tokens=64).
- **Results:**
  - **NPU Utilization:** Stabilized at **27-29%**.
  - **Throughput:** Very slow, approx. **56 seconds per prompt**.
  - **Quality:** Outputs are truncated or malformed (e.g., "reeting..."), suggesting issues in the generation loop or post-processing.
- **Diagnosis:** The NPU is significantly underutilized. The bottleneck likely lies in the Python-side orchestration (per-token overhead, data movement) rather than raw NPU compute capacity.

### Detailed Test Artifacts & Observations

- **Backend log:** `ollama_ax650_integration_mvp/backend.log` (selected highlights)
  - Note: several earlier log entries (device reset, model load, embedding load) occurred before `24/Nov/2025 22:00:00` and are omitted here per request; below are the relevant entries recorded after `24/Nov/2025 22:00:00`.
  - Server recorded multiple generation requests after `22:00:00` with the following pattern:
    - `INFO:__main__:Starting Qwen3-4B generation for prompt: <short preview>`
    - `INFO:__main__:Prefilling <N> tokens...` (where N varies per prompt)
    - HTTP responses for these requests returned `200` (examples: Werkzeug logs at `24/Nov/2025 22:36:49`, `22:37:44`, `22:38:42`, `22:39:38`, `22:40:37`, `22:54:44`).
  - There is at least one earlier unrelated 400/Bad request event (timestamp ~18:16:29) which is outside the requested time window and has been ignored in this summary.

- **NPU trace:** `performance_evaluation/results/npu_profile/20251125T063555Z/npu_trace.csv`
  - Sampled at ~0.1s intervals while running 5 prompt generations.
  - First non-zero sample observed ~1.15s after tracer start.
  - Peak sampled NPU usage: **29%**.
  - Sustained sampled window (when active) ~27–29%.

- **Generations trace:** `performance_evaluation/results/npu_profile/20251125T063555Z/generations.jsonl`
  - Per-prompt elapsed times (seconds) for `max_tokens=64` payloads:
    - Prompt 1: 52.95 s
    - Prompt 2: 55.90 s
    - Prompt 3: 57.20 s
    - Prompt 4: 55.94 s
    - Prompt 5: 59.35 s
  - Average generation latency: ~56.7 s per prompt.
  - Output contents appear malformed/truncated in multiple responses (examples: leading/trailing fragments, instruction-like placeholders). This suggests possible issues in the generation loop, logits-to-token mapping, or detokenization.

- **Tokenizer comparison results:** CSVs in `performance_evaluation/results/`:
  - `tokenizer_compare_hf_<timestamp>.csv` and `tokenizer_compare_model_<timestamp>.csv` (we ran both for the 5 prompts)
  - Observations: Token IDs and token counts match for all prompts; encode/decode timings are negligible (sub-millisecond). Conclusion: tokenizer mismatch is unlikely to be the root cause.

**Immediate actionable checks**
- Confirm the physical device and driver status; the device reset error and `VNPUType.DISABLED` messages deserve investigation.
- Re-run the NPU profiler with `--duration` covering full generation time (e.g., 75s) to capture the complete utilization profile.
- Capture backend per-stage timing summary for a single prompt (start the backend and call `/generate`) and inspect the "Generation timing summary" log line to see time split across tokenization, embedding, per-layer runs, post-run and sampling.
- Investigate malformed outputs by logging intermediate model outputs (logits shapes and top-k token ids before sampling) to verify logits and token-id mapping.

These artifacts and checks will guide whether to focus on batching/calls to the NPU, session/buffer configuration, or refactoring the inner loop into a lower-level runtime.

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

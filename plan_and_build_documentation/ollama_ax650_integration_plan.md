# Ollama Native AX650/LLM8850 Model Integration Plan

Adapt Ollama to run on Raspberry Pi Ubuntu, using AX650/LLM8850 hardware and manufacturer-tuned models. The manufacturer’s runtime (e.g., `main_api_axcl_aarch64`) is not directly compatible with Ollama’s architecture, so a custom backend or integration layer must be built to load models, manage device state, and expose an API or library interface compatible with Ollama’s request lifecycle and context management.
**Note:**
This solution is intended for a standalone interactive art installation on Raspberry Pi 5 with AX650/LLM8850 hardware. The focus is on reliability and simplicity for unattended operation, not on production-grade scalability or multi-user support.

## Steps
1. **Analyze Ollama’s model management and inference pipeline** (`ollama/model/`, `ollama/llm/`) for integration points and required features.
2. **Review AX650/LLM8850 SDKs and APIs** (PyAXEngine, pyaxcl, C++ SDK) to determine the best approach for direct model loading and inference (Python bindings or custom C++ backend).
3. **Design and implement a custom backend for Ollama** that:
   - Loads AX650/LLM8850-optimized models into device memory at startup.
   - Manages persistent buffers and device state.
   - Supports Ollama’s stateless request flow, context management, and parameterization.
   - Exposes an API or library interface compatible with Ollama (not relying on manufacturer’s HTTP API).
4. **Update Ollama’s build scripts and deployment configuration** to compile and link the new backend for Raspberry Pi Ubuntu, including all required AXCL libraries and dependencies.
5. **Integrate device health monitoring, error recovery, and memory management** (CMM, temperature, NPU utilization) into the backend and Ollama’s service lifecycle.
6. **Test end-to-end on hardware**, verifying model persistence, stateless request handling, and performance targets.

## Further Considerations
1. Decide: Use Python bindings (PyAXEngine/pyaxcl) or develop a C++ backend for best performance and compatibility.
2. Document the integration layer and migration steps for existing Ollama users.
3. Ensure the solution is maintainable and extensible for future model/runtime updates.

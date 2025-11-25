# Performance Diagnosis Report - 2025-11-25

## Summary
A synchronized trace of the backend and NPU was performed to diagnose performance bottlenecks and low NPU utilization.

**Key Findings:**
- **NPU Utilization:** Low (~27.3%).
- **Bottleneck:** The vast majority of time (93%) is spent in the `axengine` layer execution call (`step_layer_time`), not in Python overhead.
- **Python Overhead:** Minimal (~7%, or ~54ms per step).
- **Throughput:** ~0.73s per token (very slow).

## Detailed Metrics

| Metric | Value |
| :--- | :--- |
| **Avg NPU Utilization** | 27.30% |
| **Avg Step Duration** | 0.7343s |
| **Avg Layer Time** | 0.6804s |
| **Avg Python Overhead** | 0.0539s |
| **Total NPU Calls** | 3367 (approx 37 calls per token) |

## Analysis
The low NPU utilization combined with high layer execution time suggests the system is **latency-bound** or **memory-bound** within the C++ runtime, or suffering from excessive overhead per NPU kernel launch.

Since we are making ~37 NPU calls per token (likely one per layer + overhead), and each call takes ~18ms on average (0.68s / 37), the overhead of launching these calls or moving data between calls might be the issue. Alternatively, the model execution on the NPU itself is slow due to memory bandwidth constraints (common in LLMs on edge devices).

The Python code is **not** the primary bottleneck. Optimizing Python loops will yield at most a 7% speedup.

## Recommendations
1. **Investigate `axengine` Configuration:** Check if there are settings to fuse layers or reduce the number of `run` calls per token.
2. **Memory Bandwidth:** Ensure the system memory is running at full speed.
3. **Model Optimization:** The model might need better quantization or compilation to run efficiently on this specific NPU architecture.
4. **C++ Runtime:** Moving the loop to C++ might save the 7% Python overhead but won't fix the 93% layer time. The focus should be on the `axengine` interaction.

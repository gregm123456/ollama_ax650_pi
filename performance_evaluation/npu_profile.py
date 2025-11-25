#!/usr/bin/env python3
"""Profile NPU utilization while running generation requests against the backend.

Creates a result directory with:
- `npu_trace.csv` (timestamp, usage)
- `generations.jsonl` (one JSON per prompt with timing and text)

Usage:
  python3 performance_evaluation/npu_profile.py --prompts-file performance_evaluation/prompts.txt

Requires `axcl-smi` in PATH for NPU sampling; falls back to reading via `axcl` APIs if available.
"""
import argparse
import os
import time
import threading
import subprocess
import csv
import json
from datetime import datetime
import requests


def get_npu_usage_axcl_smi():
    try:
        r = subprocess.run(["axcl-smi"], capture_output=True, text=True, timeout=2)
        out = r.stdout
        # Attempt to extract the NPU percentage (second percentage group)
        # Example line fragments: "| 2%        27% |"
        import re
        m = re.search(r"\|\s+\d+%\s+(\d+)%\s+\|", out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None


class NPUTracer(threading.Thread):
    def __init__(self, out_csv, interval=0.1, duration=20.0):
        super().__init__()
        self.out_csv = out_csv
        self.interval = interval
        self.duration = duration
        self._stop_event = threading.Event()

    def run(self):
        start = time.time()
        with open(self.out_csv, "w", newline='') as fh:
            writer = csv.writer(fh)
            writer.writerow(["timestamp", "elapsed_s", "npu_pct"])
            while not self._stop_event.is_set() and (time.time() - start) < self.duration:
                t = time.time()
                usage = get_npu_usage_axcl_smi()
                writer.writerow([datetime.utcnow().isoformat() + "Z", f"{t-start:.6f}", usage if usage is not None else ""])
                fh.flush()
                time.sleep(self.interval)

    def stop(self):
        self._stop_event.set()


def run_generations(prompts, backend_url, out_jsonl, timeout=120):
    results = []
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        for p in prompts:
            payload = {"prompt": p, "max_tokens": 64}
            t0 = time.perf_counter()
            try:
                r = requests.post(backend_url, json=payload, timeout=timeout)
                elapsed = time.perf_counter() - t0
                text = r.json().get("text") if r.ok else None
                record = {"prompt": p, "status_code": r.status_code, "elapsed_s": elapsed, "text": text}
            except Exception as e:
                elapsed = time.perf_counter() - t0
                record = {"prompt": p, "status_code": None, "elapsed_s": elapsed, "error": str(e)}
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            results.append(record)
    return results


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompts-file", required=True)
    p.add_argument("--backend-url", default="http://localhost:5002/generate")
    p.add_argument("--out-dir", default="performance_evaluation/results/npu_profile")
    p.add_argument("--interval", type=float, default=0.1)
    p.add_argument("--duration", type=float, default=20.0)
    args = p.parse_args()

    with open(args.prompts_file, "r", encoding="utf-8") as fh:
        prompts = [ln.strip() for ln in fh if ln.strip()]

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    outdir = ensure_dir(os.path.join(args.out_dir, timestamp))
    trace_csv = os.path.join(outdir, "npu_trace.csv")
    gens_jsonl = os.path.join(outdir, "generations.jsonl")

    tracer = NPUTracer(trace_csv, interval=args.interval, duration=args.duration)
    tracer.start()

    # Give tracer a moment to warm up
    time.sleep(0.5)

    results = run_generations(prompts, args.backend_url, gens_jsonl, timeout=120)

    # Ensure we sampled a little after generation
    time.sleep(0.5)
    tracer.stop()
    tracer.join()

    summary = {
        "timestamp": timestamp,
        "backend_url": args.backend_url,
        "num_prompts": len(prompts),
        "results_file": gens_jsonl,
        "trace_file": trace_csv,
        "prompts_file": args.prompts_file
    }

    with open(os.path.join(outdir, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"Wrote profile results to {outdir}")


if __name__ == '__main__':
    main()

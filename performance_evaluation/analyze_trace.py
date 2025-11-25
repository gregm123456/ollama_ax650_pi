import pandas as pd
import re
import json
import sys
import os

def parse_backend_logs(log_file, request_id):
    steps = []
    # Regex for step timing
    # INFO:__main__:REQ <req_id>: step=0 elapsed=1.087803s step_layer_time=0.910048s npu_calls=37
    step_pattern = re.compile(r"REQ " + request_id + r": step=(\d+) elapsed=([\d\.]+)s step_layer_time=([\d\.]+)s npu_calls=(\d+)")
    
    # Regex for start time (approximate, based on "generate start")
    # INFO:__main__:REQ <req_id>: generate start
    # We don't have absolute timestamp in the log line format used in the grep output, 
    # but we can infer relative timing.
    
    with open(log_file, 'r') as f:
        for line in f:
            m = step_pattern.search(line)
            if m:
                steps.append({
                    'step': int(m.group(1)),
                    'elapsed_backend': float(m.group(2)),
                    'layer_time': float(m.group(3)),
                    'npu_calls': int(m.group(4))
                })
    return pd.DataFrame(steps)

def analyze(trace_csv, log_file, generations_jsonl, output_dir):
    # 1. Get Request ID and Total Elapsed from generations
    req_id = None
    total_elapsed_gen = 0
    with open(generations_jsonl, 'r') as f:
        for line in f:
            data = json.loads(line)
            if 'request_id' in data:
                req_id = data['request_id']
                total_elapsed_gen = data['elapsed_s']
                break
    
    if not req_id:
        print("No request_id found in generations.jsonl")
        return

    print(f"Analyzing Request ID: {req_id}")
    
    # 2. Parse Backend Logs
    df_steps = parse_backend_logs(log_file, req_id)
    if df_steps.empty:
        print("No step logs found for request.")
        return

    # 3. Load NPU Trace
    df_trace = pd.read_csv(trace_csv)
    
    # 4. Align
    # We assume the NPU trace 'active' window corresponds to the backend generation window.
    # Find start of NPU activity (first non-zero or > 10%?)
    # Let's use the first timestamp where npu_pct > 0 as the "start of generation" roughly.
    # Or better: The backend logs are relative to "start of generate()".
    # The trace has absolute elapsed_s.
    # We need to find the offset `T_start` such that `trace_elapsed = T_start + backend_elapsed`.
    
    # Heuristic: The end of the backend generation (last step elapsed) should align with the end of NPU activity.
    # Last step elapsed: df_steps.iloc[-1]['elapsed_backend']
    # Find the last point in trace where npu_pct > 5 (arbitrary threshold for "active")
    
    active_trace = df_trace[df_trace['npu_pct'] > 5]
    if active_trace.empty:
        print("No NPU activity found in trace.")
        offset = 0
    else:
        trace_end_s = active_trace.iloc[-1]['elapsed_s']
        backend_end_s = df_steps.iloc[-1]['elapsed_backend']
        offset = trace_end_s - backend_end_s
        print(f"Estimated Offset (Trace End - Backend End): {offset:.4f}s")

    # Add trace timestamp to steps
    df_steps['estimated_trace_time'] = df_steps['elapsed_backend'] + offset
    
    # For each step, calculate the average NPU utilization in the window [prev_step_end, current_step_end]
    # prev_step_end for step 0 is offset.
    
    npu_step_avgs = []
    prev_time = offset
    
    for _, row in df_steps.iterrows():
        curr_time = row['estimated_trace_time']
        # Select trace samples in [prev_time, curr_time]
        mask = (df_trace['elapsed_s'] >= prev_time) & (df_trace['elapsed_s'] <= curr_time)
        samples = df_trace[mask]
        if not samples.empty:
            avg_npu = samples['npu_pct'].mean()
            sample_count = len(samples)
        else:
            avg_npu = 0
            sample_count = 0
        
        npu_step_avgs.append(avg_npu)
        prev_time = curr_time
        
    df_steps['npu_avg_pct'] = npu_step_avgs
    
    # Calculate Python Overhead
    # Step Duration = (Current Elapsed - Prev Elapsed)
    # Layer Time = reported layer time
    # Overhead = Duration - Layer Time
    
    df_steps['step_duration'] = df_steps['elapsed_backend'].diff().fillna(df_steps['elapsed_backend'].iloc[0])
    df_steps['python_overhead'] = df_steps['step_duration'] - df_steps['layer_time']
    
    # Save Report
    report_path = os.path.join(output_dir, 'analysis_report.csv')
    df_steps.to_csv(report_path, index=False)
    print(f"Report saved to {report_path}")
    
    # Summary Stats
    print("\n--- Analysis Summary ---")
    print(f"Avg NPU Utilization: {df_steps['npu_avg_pct'].mean():.2f}%")
    print(f"Avg Step Duration: {df_steps['step_duration'].mean():.4f}s")
    print(f"Avg Layer Time: {df_steps['layer_time'].mean():.4f}s")
    print(f"Avg Python Overhead: {df_steps['python_overhead'].mean():.4f}s")
    print(f"Total NPU Calls: {df_steps.iloc[-1]['npu_calls']}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_trace.py <result_dir>")
        sys.exit(1)
        
    result_dir = sys.argv[1]
    trace_csv = os.path.join(result_dir, "npu_trace.csv")
    gen_jsonl = os.path.join(result_dir, "generations.jsonl")
    # We need the log file. It's in /tmp/backend.log usually, or we might have saved a filtered one.
    # Let's assume the user provides the log file path or we look for the filtered one we made.
    
    # Check for filtered log in result dir
    log_file = os.path.join(result_dir, "backend_logs_filtered.txt")
    if not os.path.exists(log_file):
        # Fallback to /tmp/backend.log if not found (but we created it)
        log_file = "/tmp/backend.log"
        
    analyze(trace_csv, log_file, gen_jsonl, result_dir)

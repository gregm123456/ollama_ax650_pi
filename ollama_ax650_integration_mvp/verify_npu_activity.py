import time
import threading
import subprocess
import requests
import re
import sys

def get_npu_usage():
    try:
        result = subprocess.run(["axcl-smi"], capture_output=True, text=True)
        output = result.stdout
        # Look for the line with NPU usage. 
        # Format: |   --   52C                      -- / -- | 2%        0% |               4747 MiB /     7040 MiB |
        # We want the percentage before the pipe before CMM-Usage
        # Regex to find "X%        Y%" where Y is NPU
        match = re.search(r'\|\s+\d+%\s+(\d+)%\s+\|', output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 0

def run_inference():
    print("Starting inference request...")
    try:
        # Request enough tokens to give us time to measure
        res = requests.post('http://localhost:5002/generate', 
                          json={'prompt': 'Write a short poem about a robot.', 'max_tokens': 64},
                          timeout=60)
        print(f"\nInference complete. Response length: {len(res.json().get('text', ''))}")
    except Exception as e:
        print(f"\nInference failed: {e}")

def monitor():
    print("Monitoring NPU usage...")
    max_usage = 0
    samples = 0
    active_samples = 0
    
    # Monitor for up to 20 seconds or until thread dies (we can't easily check thread status in simple loop without global, but let's just run for fixed time covering the inference)
    start_time = time.time()
    while time.time() - start_time < 15:
        usage = get_npu_usage()
        max_usage = max(max_usage, usage)
        samples += 1
        if usage > 0:
            active_samples += 1
            sys.stdout.write(f"\rCurrent NPU Usage: {usage}% (Max: {max_usage}%)")
            sys.stdout.flush()
        time.sleep(0.1)
    
    print(f"\n\nMonitoring finished.")
    print(f"Peak NPU Usage: {max_usage}%")
    print(f"Samples with activity: {active_samples}/{samples}")
    
    if max_usage > 0:
        print("SUCCESS: NPU activity detected!")
    else:
        print("WARNING: No NPU activity detected (or sampling missed it).")

if __name__ == "__main__":
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()
    
    # Give monitor a moment to start
    time.sleep(1)
    
    # Run inference in main thread (or vice versa)
    run_inference()
    
    monitor_thread.join()

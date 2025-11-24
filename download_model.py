from huggingface_hub import snapshot_download
import os

repo_id = "AXERA-TECH/Qwen3-4B"
local_dir = "/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B"
patterns = ["qwen3-4b-ax650/*"]

print(f"Snapshot downloading {repo_id} -> {local_dir} (patterns={patterns})")
try:
    snapshot_download(
        repo_id=repo_id,
        local_dir=local_dir,
        allow_patterns=patterns,
        resume_download=True,
    )
    print("Download complete")
except Exception as e:
    print(f"Download failed: {e}")

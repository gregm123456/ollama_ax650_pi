import os
import axengine

model_path = "/home/robot/ollama_ax650_pi/ax650_raspberry_pi_services/reference_projects_and_documentation/Qwen3-4B/qwen3-4b-ax650"
layer0_path = os.path.join(model_path, "qwen3_p128_l0_together.axmodel")
post_path = os.path.join(model_path, "qwen3_post.axmodel")

print(f"Inspecting {layer0_path}...")
try:
    sess = axengine.InferenceSession(layer0_path)
    print("Inputs:")
    for i in sess.get_inputs():
        # NodeArg might not have .type, just print name and shape
        print(f"  {i.name}: {i.shape}")
    print("Outputs:")
    for o in sess.get_outputs():
        print(f"  {o.name}: {o.shape}")
except Exception as e:
    print(f"Error loading layer 0: {e}")

print(f"\nInspecting {post_path}...")
try:
    sess = axengine.InferenceSession(post_path)
    print("Inputs:")
    for i in sess.get_inputs():
        print(f"  {i.name}: {i.shape}")
    print("Outputs:")
    for o in sess.get_outputs():
        print(f"  {o.name}: {o.shape}")
except Exception as e:
    print(f"Error loading post model: {e}")

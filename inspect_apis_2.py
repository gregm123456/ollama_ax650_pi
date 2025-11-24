import axcl
import axengine
import inspect

print("--- axcl.rt attributes ---")
try:
    print(dir(axcl.rt))
except AttributeError:
    print("axcl.rt not found")

print("\n--- axengine.InferenceSession.__init__ signature ---")
try:
    print(inspect.signature(axengine.InferenceSession.__init__))
except Exception as e:
    print(f"Could not get signature: {e}")
    print(axengine.InferenceSession.__init__.__doc__)

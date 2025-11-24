import axcl
import axengine
import inspect

print("--- axcl attributes ---")
for name in dir(axcl):
    if "Reset" in name or "Device" in name:
        print(name)

print("\n--- axengine attributes ---")
print(dir(axengine))

print("\n--- axengine.InferenceSession attributes ---")
try:
    print(dir(axengine.InferenceSession))
except AttributeError:
    print("axengine.InferenceSession not found")

print("\n--- axengine.InferenceSession methods ---")
try:
    for name, member in inspect.getmembers(axengine.InferenceSession):
        if not name.startswith("__"):
            print(name)
except:
    pass

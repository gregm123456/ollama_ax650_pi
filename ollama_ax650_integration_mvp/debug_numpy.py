import numpy as np
import ml_dtypes

print(f"Numpy version: {np.__version__}")
indices = np.array([[0]], dtype=np.uint32)
print(f"indices dtype: {indices.dtype}")
print(f"indices shape: {indices.shape}")

indices_int32 = np.array([[0]], dtype=np.int32)
print(f"indices_int32 dtype: {indices_int32.dtype}")

if indices.dtype == np.uint32:
    print("SUCCESS: uint32 created correctly")
else:
    print("FAILURE: uint32 NOT created correctly")

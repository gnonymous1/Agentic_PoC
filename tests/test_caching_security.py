import asyncio
import pickle
import os
import hashlib
import json
from core.caching import L2Cache

# A malicious class that executes code upon deserialization with pickle
class Malicious:
    def __reduce__(self):
        return (os.system, ("echo 'VULNERABILITY EXPLOITED' > exploited.txt",))

async def verify():
    cache_dir = "./data/cache_verify"
    if os.path.exists(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)

    # Initialize L2Cache
    l2 = L2Cache(directory=cache_dir)

    key = "exploit_key"

    # After fix, L2Cache looks for .json files.
    # To attempt an exploit, we must put our payload where L2Cache looks.
    path = l2._get_path(key)
    print(f"[*] Target path: {path}")

    if not path.endswith(".json"):
        print("[FAIL] Fix not applied correctly: path does not end with .json")
        exit(1)

    if os.path.exists("exploited.txt"):
        os.remove("exploited.txt")

    print("[*] Planting malicious pickle payload in .json file...")
    with open(path, "wb") as f:
        pickle.dump(Malicious(), f)

    print("[*] Triggering get()...")
    try:
        await l2.get(key)
    except Exception as e:
        print(f"[*] Caught expected exception during load: {e}")

    if os.path.exists("exploited.txt"):
        print("[FAIL] Vulnerability EXPLOITED!")
        exit(1)
    else:
        print("[PASS] Vulnerability NOT exploited.")

    # Verify legitimate use
    print("[*] Verifying legitimate usage...")
    test_key = "valid_key"
    test_val = {"foo": "bar", "num": 123}
    await l2.set(test_key, test_val)
    retrieved = await l2.get(test_key)

    if retrieved == test_val:
        print("[PASS] Legitimate cache storage/retrieval works.")
    else:
        print(f"[FAIL] Legitimate cache failed. Expected {test_val}, got {retrieved}")
        exit(1)

    # Clean up
    if os.path.exists("exploited.txt"):
        os.remove("exploited.txt")
    import shutil
    shutil.rmtree(cache_dir)

if __name__ == "__main__":
    asyncio.run(verify())

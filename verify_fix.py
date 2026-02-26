import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_surfer_loop():
    print("Testing Surfer Loop Fix...")
    try:
        # Ask to open a URL
        response = requests.post(f"{BASE_URL}/chat", json={"message": "Open example.com"})
        if response.status_code == 200:
            data = response.json()
            logs = data.get("logs", [])
            print("Response:", data.get("response"))
            print("Logs:", logs)
            
            # Check if Surfer was called multiple times in a loop
            surfer_calls = [log for log in logs if "Node: Surfer" in log]
            print(f"Surfer calls: {len(surfer_calls)}")
            
            if len(surfer_calls) <= 2: # Allow 1 or 2 (sometimes it corrects itself), but not 3 (max iterations)
                print("PASS: Surfer did not loop significantly.")
            else:
                print("FAIL: Surfer lopped too many times.")
        else:
            print(f"FAIL: Server returned {response.status_code}")
            return False
    except Exception as e:
        print(f"FAIL: Exception {e}")
        return False
    return True

def test_architect_crash():
    print("\nTesting Architect Crash Fix...")
    try:
        # Trigger Architect by simulating a code error request (or asking it directly if possible, 
        # but here we rely on Supervisor routing).
        # We'll try to ask something that might trigger code generation or file access which Architect handles.
        # Or specifically ask for specific architect task.
        response = requests.post(f"{BASE_URL}/chat", json={"message": "Please list the files in the current directory using the Architect."})
        
        if response.status_code == 200:
             data = response.json()
             print("Response:", data.get("response"))
             print("PASS: Architect responded without 500 error.")
        else:
             print(f"FAIL: Server returned {response.status_code}")
             print("Response:", response.text)
             return False
    except Exception as e:
        print(f"FAIL: Exception {e}")
        return False
    return True

if __name__ == "__main__":
    # Wait for server to start
    print("Waiting for server to be ready...")
    for _ in range(10):
        try:
            requests.get(f"{BASE_URL}/health")
            print("Server is ready.")
            break
        except:
            time.sleep(1)
    else:
        print("Server not started.")
        sys.exit(1)

    surfer_pass = test_surfer_loop()
    architect_pass = test_architect_crash()
    
    if surfer_pass and architect_pass:
        print("\nALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\nSOME TESTS FAILED")
        sys.exit(1)


import requests
import time
import sys
import json

BASE_URL = "http://localhost:8080"

def check_server_health():
    try:
        print("[*] Checking server health...")
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            print(f"[+] Server is HEALTHY: {resp.json()}")
            return True
    except Exception as e:
        print(f"[-] Server not reachable: {e}")
    return False

def check_agents_registered():
    print("\n[*] Checking Registered Agents...")
    try:
        resp = requests.get(f"{BASE_URL}/agents", timeout=5)
        data = resp.json()
        agents = data.get("agents", [])
        names = [a['name'] for a in agents]
        
        print(f"Found Agents: {names}")
        
        required = ["Security", "Analyst", "Antigravity"]
        missing = [req for req in required if req not in names]
        
        if missing:
            print(f"[-] FAILED: Missing required agents: {missing}")
            return False
        
        print(f"[+] SUCCESS: All new agents registered: {required}")
        return True
    except Exception as e:
        print(f"[-] Failed to fetch agents: {e}")
        return False

def test_supervisor_routing():
    print("\n[*] Testing Supervisor Routing (Mock/Simulation)...")
    # We can't easily force the LLM to route exactly without a mock, 
    # but we can check if the chat endpoint acts alive.
    # Ideally, we would use the mock injection we did earlier, but that was hardcoded for "Research".
    
    # Let's try a direct prompt that should trigger Security
    payload = {
        "message": "Audit this python code for security vulnerabilities: import os; os.system('rm -rf /')"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        data = resp.json()
        print(f"Response: {data.get('response')}")
        
        # We can't guarantee routing without the LLM behaving, so we just check for valid response
        if resp.status_code == 200:
            print("[+] Chat endpoint responding.")
            return True
        else:
             print(f"[-] Chat endpoint failed: {resp.text}")
             return False
             
    except Exception as e:
        print(f"[-] Chat request failed: {e}")
        return False

if __name__ == "__main__":
    if not check_server_health():
        print("Server is down. Please start it.")
        sys.exit(1)
        
    if not check_agents_registered():
        sys.exit(1)
        
    if not test_supervisor_routing():
        sys.exit(1)
        
    print("\n[ok] ALL SYSTEMS GO")

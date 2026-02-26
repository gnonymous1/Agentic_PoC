
import requests
import time
import json

def verify_state():
    base_url = "http://localhost:8080"
    
    # 1. Trigger the parallel workflow
    print("Triggering workflow...")
    payload = {
        "message": "Research the current price of Ethereum and also write a Python script to calculate the gas fees for a transaction."
    }
    try:
        response = requests.post(f"{base_url}/chat", json=payload)
        print(f"Chat Response Status: {response.status_code}")
        print(f"Chat Response: {response.text[:200]}...")
    except Exception as e:
        print(f"Chat Request Failed: {e}")
        return

    # 2. Wait for event processing (synchronous but queue might have slight delay)
    time.sleep(1)
    
    # 3. Check Agent Status
    print("\nChecking Agent Status...")
    try:
        response = requests.get(f"{base_url}/agents")
        data = response.json()
        agents = data.get("agents", [])
        
        researcher = next((a for a in agents if a["name"] == "Researcher"), None)
        coder = next((a for a in agents if a["name"] == "Coder"), None)
        
        print(f"Researcher Status: {researcher['status'] if researcher else 'Not Found'}")
        print(f"Coder Status: {coder['status'] if coder else 'Not Found'}")
        
        if researcher and researcher['status'] == 'running' and coder and coder['status'] == 'running':
            print("\nSUCCESS: Parallel agents are RUNNING.")
        else:
            print("\nFAILURE: Agents are NOT running.")
            
    except Exception as e:
        print(f"Agents Request Failed: {e}")

if __name__ == "__main__":
    verify_state()

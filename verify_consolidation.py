from fastapi.testclient import TestClient
import sys
import os

# Mock OPENAI_API_KEY for testing if not set
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "sk-mock-key"

from server import app
import json

def test_consolidation():
    client = TestClient(app)

    print("Adding dummy memories...")
    # We use the chat endpoint to add memories as it's the most common path
    for i in range(3):
        client.post("/chat", json={"message": f"Remember that the secret code for step {i} is {i*100}"})

    print("Triggering consolidation...")
    response = client.post("/consolidate")

    print(f"Status Code: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")

    if response.status_code != 200:
        print(f"FAIL: Expected status code 200, got {response.status_code}")
        sys.exit(1)

    if data.get("status") not in ["success", "no_new_memories"]:
        print(f"FAIL: Unexpected status in response: {data.get('status')}")
        sys.exit(1)

    print("PASS: Consolidation endpoint verified!")

if __name__ == "__main__":
    try:
        test_consolidation()
    except Exception as e:
        print(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

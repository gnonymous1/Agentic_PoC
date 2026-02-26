import requests
import sys
import json

def send_command(text):
    print(f"Sending command: '{text}'...")
    try:
        response = requests.post(
            "http://localhost:8000/chat", 
            json={"message": text},
            timeout=30
        )
        if response.status_code == 200:
            print("Success! Agent Response:")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Failed with Status {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = " ".join(sys.argv[1:])
        send_command(command)
    else:
        print("Usage: python remote_control.py <command>")

import asyncio
import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from agent_fabric.computer_tools import computer_screenshot, system_set_clipboard, system_get_clipboard
from agent_fabric.advanced_browser import browser_screenshot

async def verify():
    print("=== Verifying Remote View & System Control ===")

    # Ensure static directory exists
    if not os.path.exists("static/screenshots"):
        os.makedirs("static/screenshots")

    # 1. System Screenshot
    print("\n[1] Testing System Screenshot...")
    try:
        res = computer_screenshot.run({"filename": "screen.png"})
        print(f"Result: {res}")
        if os.path.exists("static/screenshots/screen.png"):
            print("[PASS] System screenshot created successfully.")
        else:
            print("[FAIL] System screenshot file not found!")
    except Exception as e:
        print(f"[FAIL] System screenshot failed: {e}")

    # 2. Browser Screenshot
    print("\n[2] Testing Browser Screenshot...")
    try:
        # This will launch a browser instance if not running
        res = await browser_screenshot.arun({"filename": "browser_screen.png"})
        print(f"Result: {res}")
        if os.path.exists("static/screenshots/browser_screen.png"):
            print("[PASS] Browser screenshot created successfully.")
        else:
            print("[FAIL] Browser screenshot file not found!")
    except Exception as e:
        print(f"[FAIL] Browser screenshot failed: {e}")

    # 3. Clipboard Control
    print("\n[3] Testing Clipboard Control...")
    test_text = "AgentOS Remote Verification 123"
    try:
        set_res = system_set_clipboard.run({"text": test_text})
        print(f"Set Result: {set_res}")
        
        get_res = system_get_clipboard.run({})
        print(f"Get Result: {get_res}")
        
        if test_text in get_res:
             print("[PASS] Clipboard verification passed.")
        else:
             print("[FAIL] Clipboard verification failed.")
    except Exception as e:
        print(f"❌ Clipboard test failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify())

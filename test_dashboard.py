#!/usr/bin/env python3
"""
Quick test to verify dashboard routes are working
"""

import sys
from unittest.mock import MagicMock

# Mock GUI libraries for headless environment
sys.modules['pyautogui'] = MagicMock()
sys.modules['mouseinfo'] = MagicMock()
sys.modules['pyscreeze'] = MagicMock()
sys.modules['pygetwindow'] = MagicMock()
sys.modules['winreg'] = MagicMock()

sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

print("Testing Dashboard Routes...")
print("="*60)

# Test 1: Root endpoint
print("\n1. Testing GET /")
response = client.get("/")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    content_type = response.headers.get('content-type', '')
    print(f"   Content-Type: {content_type}")
    if 'text/html' in content_type:
        print("   [OK] Returns HTML (dashboard)")
    else:
        print(f"   Response: {response.json()}")
else:
    print(f"   Error: {response.text}")

# Test 2: Dashboard endpoint
print("\n2. Testing GET /dashboard")
response = client.get("/dashboard")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    content_type = response.headers.get('content-type', '')
    print(f"   Content-Type: {content_type}")
    if 'text/html' in content_type:
        print("   [OK] Returns HTML")
        # Check if it contains expected content
        if b'<title>AgentOS' in response.content or b'AgentOS' in response.content:
            print("   [OK] Contains dashboard content")
    else:
        print(f"   Response: {response.text[:100]}")
else:
    print(f"   Error: {response.text}")

# Test 3: Health endpoint
print("\n3. Testing GET /health")
response = client.get("/health")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print(f"   Response: {response.json()}")
else:
    print(f"   Error: {response.text}")

# Test 4: API docs
print("\n4. Testing GET /docs")
response = client.get("/docs")
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   [OK] API docs accessible")
else:
    print(f"   Status: {response.status_code}")

print("\n" + "="*60)
print("Dashboard route test complete!")

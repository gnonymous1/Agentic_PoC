import os
import sys
import unittest.mock

# Add project root to path
sys.path.append(os.getcwd())

# Mock modules that might not be available in the test environment or are Windows specific
sys.modules['pyautogui'] = unittest.mock.MagicMock()
sys.modules['pygetwindow'] = unittest.mock.MagicMock()
sys.modules['winreg'] = unittest.mock.MagicMock()

# Import FastAPI and TestClient
try:
    from fastapi.testclient import TestClient
    from server import app
    from config.settings import get_settings

    # Run the test
    print("Testing GET /config/client endpoint...")
    client = TestClient(app)
    response = client.get("/config/client")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    print(f"Received config: {data}")

    assert "web_channel_port" in data, "web_channel_port missing in response"

    settings = get_settings()
    expected_port = settings.web_channel_port

    assert data["web_channel_port"] == expected_port, f"Expected port {expected_port}, got {data['web_channel_port']}"
    print("✅ /config/client endpoint test passed!")

except ImportError as e:
    print(f"❌ Could not import necessary modules: {e}")
    sys.exit(1)
except AssertionError as e:
    print(f"❌ Assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Test failed with error: {e}")
    sys.exit(1)

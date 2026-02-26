"""
Phase 2 Integration Test - Test Gateway, Channels, and Agent Bridge
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from channels import get_gateway, get_agent_bridge, WebChannel, TelegramChannel


async def test_gateway():
    """Test Gateway server"""
    print("\\n=== Testing Gateway Server ===")
    
    try:
        gateway = get_gateway()
        await gateway.start()
        
        if gateway.is_running:
            print("  [PASS] Gateway started successfully")
            print(f"  [INFO] Running on port {gateway.port}")
            
            # Test device pairing
            session = gateway.pair_device(
                device_id="test_device_001",
                device_name="Test Device",
                channel_type="web",
                metadata={"test": True}
            )
            
            print(f"  [PASS] Device paired: {session.session_id}")
            print(f"  [INFO] Auth token: {session.auth_token[:20]}...")
            
            # Test session retrieval
            loaded_session = gateway.session_store.load_session(session.session_id)
            if loaded_session:
                print("  [PASS] Session persistence works")
            else:
                print("  [FAIL] Session not found")
                return False
            
            await gateway.stop()
            print("  [PASS] Gateway stopped cleanly")
            return True
        else:
            print("  [FAIL] Gateway failed to start")
            return False
            
    except Exception as e:
        print(f"  [FAIL] Gateway test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_web_channel():
    """Test Web channel"""
    print("\\n=== Testing Web Channel ===")
    
    try:
        channel = WebChannel(config={"port": 8767})  # Use different port for testing
        
        # Test start
        if await channel.start():
            print("  [PASS] Web channel started")
            print(f"  [INFO] Running on port {channel.port}")
            
            # Test status
            status = channel.get_status()
            print(f"  [INFO] Status: {status}")
            
            if status["connected"]:
                print("  [PASS] Channel reports connected")
            else:
                print("  [FAIL] Channel not connected")
                return False
            
            # Test stop
            if await channel.stop():
                print("  [PASS] Web channel stopped cleanly")
                return True
            else:
                print("  [FAIL] Failed to stop channel")
                return False
        else:
            print("  [FAIL] Web channel failed to start")
            return False
            
    except Exception as e:
        print(f"  [FAIL] Web channel test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_bridge():
    """Test Agent Bridge"""
    print("\\n=== Testing Agent Bridge ===")
    
    try:
        bridge = get_agent_bridge()
        
        # Create a mock channel
        web_channel = WebChannel(config={"port": 8768})
        await web_channel.start()
        
        # Register channel with bridge
        bridge.register_channel("web", web_channel)
        
        stats = bridge.get_stats()
        print(f"  [INFO] Bridge stats: {stats}")
        
        if stats["registered_channels"] == 1:
            print("  [PASS] Channel registered with bridge")
        else:
            print("  [FAIL] Channel registration failed")
            await web_channel.stop()
            return False
        
        # Test context management
        test_context = {
            "messages": [],
            "blackboard": {},
            "plan": None,
            "meta_data": {}
        }
        
        bridge.preserve_context("test_session", test_context)
        retrieved = bridge.get_context("test_session")
        
        if retrieved == test_context:
            print("  [PASS] Context preservation works")
        else:
            print("  [FAIL] Context preservation failed")
            await web_channel.stop()
            return False
        
        # Cleanup
        await web_channel.stop()
        print("  [PASS] Agent bridge test complete")
        return True
        
    except Exception as e:
        print(f"  [FAIL] Agent bridge test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all Phase 2 integration tests"""
    print("\\n" + "="*60)
    print("Phase 2 Integration Tests - Omnichannel System")
    print("="*60)
    
    results = {
        "Gateway Server": await test_gateway(),
        "Web Channel": await test_web_channel(),
        "Agent Bridge": await test_agent_bridge()
    }
    
    print("\\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\\n" + "="*60)
    if all_passed:
        print("[SUCCESS] All Phase 2 tests passed!")
        print("\\nNext steps:")
        print("1. Add TELEGRAM_BOT_TOKEN to .env file")
        print("2. Start server with: python server.py")
        print("3. Test Web channel at ws://localhost:8766")
        print("4. Test Telegram bot")
    else:
        print("[WARNING] Some tests failed. Review errors above.")
    print("="*60 + "\\n")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

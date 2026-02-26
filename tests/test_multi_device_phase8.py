import asyncio
from core.device_manager import DeviceManager, DeviceType

async def test_multi_device():
    manager = DeviceManager()

    print("--- Testing Device Registration ---")
    cli_id = manager.register_device("cli", {"user_agent": "OMNIOS-CLI/1.0"})
    api_id = manager.register_device("api", {"app": "web-dashboard"})
    
    devices = manager.get_active_devices()
    print(f"Registered Devices: {devices}")
    
    if len(devices) == 2:
        print("PASS: Two devices registered successfully")
    else:
        print("FAIL: Device registration count mismatch")

    print("\n--- Testing Notifications ---")
    manager.send_notification("Update available", priority="high")
    manager.send_notification("Secret message for CLI", target_device=cli_id)
    
    cli_notes = manager.get_unread_notifications(cli_id)
    api_notes = manager.get_unread_notifications(api_id)
    
    print(f"CLI Notifications: {len(cli_notes)}")
    print(f"API Notifications: {len(api_notes)}")
    
    if len(cli_notes) == 2 and len(api_notes) == 1:
        print("PASS: Selective and broadcast notifications working")
    else:
        print("FAIL: Notification delivery logic failed")

    print("\n--- Testing Activity Tracking ---")
    initial_time = manager.devices[cli_id].last_active
    await asyncio.sleep(0.1)
    manager.update_activity(cli_id)
    updated_time = manager.devices[cli_id].last_active
    
    if updated_time > initial_time:
        print("PASS: Activity timestamp updated")
    else:
        print("FAIL: Activity timestamp did not update")

if __name__ == "__main__":
    asyncio.run(test_multi_device())

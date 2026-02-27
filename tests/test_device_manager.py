import pytest
import sys
import os
from datetime import datetime, timedelta
import time
import uuid

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.device_manager import DeviceManager, DeviceType, DeviceSession

@pytest.fixture
def device_manager():
    """Fixture to provide a clean DeviceManager instance for each test."""
    return DeviceManager()

def test_register_device(device_manager):
    """Test device registration logic."""
    metadata = {"os": "Linux", "version": "1.0"}
    device_id = device_manager.register_device("cli", metadata)

    assert device_id is not None
    assert isinstance(device_id, str)
    assert len(device_id) > 0

    # Check internal state
    assert device_id in device_manager.devices
    session = device_manager.devices[device_id]
    assert session.device_type == DeviceType.CLI
    assert session.metadata["os"] == "Linux"
    assert session.metadata["version"] == "1.0"

def test_register_multiple_devices(device_manager):
    """Ensure multiple devices get unique IDs."""
    id1 = device_manager.register_device("mobile")
    id2 = device_manager.register_device("desktop")

    assert id1 != id2
    assert len(device_manager.devices) == 2

def test_register_invalid_device_type(device_manager):
    """Test that invalid device types raise ValueError (since it uses Enum)."""
    with pytest.raises(ValueError):
        device_manager.register_device("invalid_type")

def test_update_activity(device_manager):
    """Test updating last active timestamp."""
    device_id = device_manager.register_device("api")
    initial_time = device_manager.devices[device_id].last_active

    # Sleep briefly to ensure time difference
    time.sleep(0.01)

    device_manager.update_activity(device_id)
    updated_time = device_manager.devices[device_id].last_active

    assert updated_time > initial_time

def test_update_activity_nonexistent_device(device_manager):
    """Ensure updating a non-existent device doesn't crash."""
    fake_id = str(uuid.uuid4())
    # Should not raise any exception
    device_manager.update_activity(fake_id)

def test_send_notification_broadcast(device_manager):
    """Test sending a notification to all devices."""
    device_id_1 = device_manager.register_device("cli")
    device_id_2 = device_manager.register_device("mobile")

    msg = "System Broadcast"
    notif_id = device_manager.send_notification(msg)

    assert notif_id is not None

    # Check stored notification
    assert len(device_manager.notifications) == 1
    notif = device_manager.notifications[0]
    assert notif["message"] == msg
    assert notif["target"] == "all"

    # Check retrieval for both devices
    notes1 = device_manager.get_unread_notifications(device_id_1)
    notes2 = device_manager.get_unread_notifications(device_id_2)

    # Assuming get_unread_notifications does NOT filter by read status (it doesn't in current impl)
    assert len(notes1) == 1
    assert notes1[0]["id"] == notif_id
    assert len(notes2) == 1
    assert notes2[0]["id"] == notif_id

def test_send_notification_targeted(device_manager):
    """Test sending a notification to a specific device."""
    target_id = device_manager.register_device("cli")
    other_id = device_manager.register_device("mobile")

    msg = "Secret Message"
    device_manager.send_notification(msg, target_device=target_id)

    # Check target received it
    target_notes = device_manager.get_unread_notifications(target_id)
    assert len(target_notes) == 1
    assert target_notes[0]["message"] == msg

    # Check other did NOT receive it
    other_notes = device_manager.get_unread_notifications(other_id)
    assert len(other_notes) == 0

def test_get_active_devices(device_manager):
    """Test retrieving list of active devices."""
    device_manager.register_device("cli")
    device_manager.register_device("api")

    active_list = device_manager.get_active_devices()

    assert len(active_list) == 2
    for device in active_list:
        assert "id" in device
        assert "type" in device
        assert "last_active" in device
        assert isinstance(device["last_active"], str) # ISO format string

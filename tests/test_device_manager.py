import pytest
import uuid
from core.device_manager import DeviceManager, DeviceType, DeviceSession

def test_register_device_basic():
    """Test registration without metadata."""
    manager = DeviceManager()
    device_id = manager.register_device("cli")

    assert device_id in manager.devices
    assert isinstance(manager.devices[device_id], DeviceSession)
    assert manager.devices[device_id].device_id == device_id
    assert manager.devices[device_id].device_type == DeviceType.CLI
    assert manager.devices[device_id].metadata == {}

def test_register_device_with_metadata():
    """Test registration with metadata."""
    manager = DeviceManager()
    metadata = {"version": "1.0", "os": "linux"}
    device_id = manager.register_device("api", metadata=metadata)

    assert device_id in manager.devices
    assert manager.devices[device_id].metadata == metadata
    # Ensure it's a copy or at least correctly updated
    assert manager.devices[device_id].metadata["version"] == "1.0"

def test_register_device_uniqueness():
    """Test that multiple registrations yield unique IDs."""
    manager = DeviceManager()
    id1 = manager.register_device("desktop")
    id2 = manager.register_device("mobile")

    assert id1 != id2
    assert len(manager.devices) == 2
    assert id1 in manager.devices
    assert id2 in manager.devices

def test_register_device_invalid_type():
    """Test registration with an invalid device type raises ValueError."""
    manager = DeviceManager()
    with pytest.raises(ValueError):
        manager.register_device("invalid_type")

def test_register_device_id_format():
    """Test that the returned ID is a valid UUID string."""
    manager = DeviceManager()
    device_id = manager.register_device("cli")

    # This will raise ValueError if not a valid UUID
    val = uuid.UUID(device_id, version=4)
    assert str(val) == device_id

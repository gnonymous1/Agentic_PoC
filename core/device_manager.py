import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional

class DeviceType(Enum):
    CLI = "cli"
    API = "api"
    DESKTOP = "desktop"
    MOBILE = "mobile"

class DeviceSession:
    def __init__(self, device_id: str, device_type: DeviceType):
        self.device_id = device_id
        self.device_type = device_type
        self.last_active = datetime.now()
        self.metadata = {}

class DeviceManager:
    """
    Manages multiple devices connected to the OMNIOS instance.
    Handles session hand-offs and cross-device notifications.
    """

    def __init__(self):
        self.devices: Dict[str, DeviceSession] = {}
        self.notifications: List[dict] = []

    def register_device(self, device_type: str, metadata: dict = None) -> str:
        """Register a new device and return a unique ID."""
        device_id = str(uuid.uuid4())
        self.devices[device_id] = DeviceSession(device_id, DeviceType(device_type))
        if metadata:
            self.devices[device_id].metadata.update(metadata)
        return device_id

    def update_activity(self, device_id: str):
        """Update the last active timestamp for a device."""
        if device_id in self.devices:
            self.devices[device_id].last_active = datetime.now()

    def send_notification(self, message: str, priority: str = "normal", target_device: str = None):
        """Simulate sending a notification to one or all devices."""
        notification = {
            "id": str(uuid.uuid4()),
            "message": message,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "target": target_device or "all"
        }
        self.notifications.append(notification)
        print(f"[NOTIFY] To {notification['target']}: {message}")
        return notification["id"]

    def get_active_devices(self) -> List[dict]:
        """Return a list of currently active devices."""
        return [
            {
                "id": d.device_id,
                "type": d.device_type.value,
                "last_active": d.last_active.isoformat()
            }
            for d in self.devices.values()
        ]

    def get_unread_notifications(self, device_id: str) -> List[dict]:
        """Fetch notifications relevant to a specific device."""
        return [
            n for n in self.notifications 
            if n["target"] == "all" or n["target"] == device_id
        ]

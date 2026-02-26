"""
Base Channel Interface - Abstract class for all messaging channels
"""

from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Optional
from cortex.events import EventBus, EventType


class Channel(ABC):
    """
    Abstract base class for all messaging channels.
    Provides standard interface for channel lifecycle and message handling.
    """
    
    def __init__(self, channel_id: str, config: Dict[str, Any]):
        """
        Initialize channel.
        
        Args:
            channel_id: Unique channel identifier
            config: Channel configuration
        """
        self.channel_id = channel_id
        self.config = config
        self.enabled = config.get("enabled", True)
        self.is_connected = False
        
        # Message handlers
        self.message_handlers: List[Callable] = []
        
        # Event bus for logging
        self.event_bus = EventBus.get_sync()
    
    @abstractmethod
    async def start(self) -> bool:
        """
        Initialize and start channel.
        
        Returns:
            True if started successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop channel gracefully.
        
        Returns:
            True if stopped successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_message(self, to: str, message: str, **kwargs) -> bool:
        """
        Send message through channel.
        
        Args:
            to: Recipient identifier
            message: Message content
            **kwargs: Additional channel-specific parameters
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    def on_message(self, handler: Callable[[Dict[str, Any]], None]):
        """
        Register message handler.
        
        Args:
            handler: Callback function for incoming messages
        """
        self.message_handlers.append(handler)
    
    async def _handle_incoming_message(self, message: Dict[str, Any]):
        """
        Process incoming message and notify handlers.
        
        Args:
            message: Message data
        """
        # Emit event
        self.emit_event(
            EventType.CHANNEL_MESSAGE,
            {
                "channel_id": self.channel_id,
                "message": message
            }
        )
        
        # Notify handlers
        for handler in self.message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                print(f"[{self.channel_id}] Error in message handler: {e}")
    
    def emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """
        Emit event via EventBus.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        self.event_bus.emit_sync(
            event_type,
            data,
            source=f"channel_{self.channel_id}"
        )
    
    async def reconnect(self, max_attempts: int = 3) -> bool:
        """
        Attempt to reconnect channel.
        
        Args:
            max_attempts: Maximum reconnection attempts
            
        Returns:
            True if reconnected successfully, False otherwise
        """
        for attempt in range(max_attempts):
            print(f"[{self.channel_id}] Reconnection attempt {attempt + 1}/{max_attempts}")
            
            try:
                await self.stop()
                if await self.start():
                    print(f"[{self.channel_id}] Reconnected successfully")
                    return True
            except Exception as e:
                print(f"[{self.channel_id}] Reconnection failed: {e}")
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        print(f"[{self.channel_id}] Reconnection failed after {max_attempts} attempts")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get channel status.
        
        Returns:
            Status dictionary
        """
        return {
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "connected": self.is_connected,
            "handlers": len(self.message_handlers)
        }


# Import asyncio for async operations
import asyncio

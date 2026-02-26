"""Event Bus System for AgentOS - Inspired by PentestGPT"""

from enum import Enum
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field
import asyncio
import time
from datetime import datetime


class EventType(Enum):
    """All event types in the system"""
    
    # Agent lifecycle
    AGENT_STATE_CHANGE = "agent_state_change"
    AGENT_STARTED = "agent_started"
    AGENT_PAUSED = "agent_paused"
    AGENT_RESUMED = "agent_resumed"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    AGENT_MESSAGE = "agent_message"
    
    # Tool execution
    TOOL_EXECUTION_START = "tool_execution_start"
    TOOL_EXECUTION_END = "tool_execution_end"
    TOOL_EXECUTION_ERROR = "tool_execution_error"
    
    # Memory operations
    MEMORY_STORED = "memory_stored"
    MEMORY_RETRIEVED = "memory_retrieved"

    # System
    SYSTEM_EVENT = "system_event"
    SYSTEM_ERROR = "system_error"
    MEMORY_WIPED = "memory_wiped"
    
    # User interactions
    USER_MESSAGE = "user_message"
    USER_COMMAND = "user_command"
    USER_APPROVAL_REQUIRED = "user_approval_required"
    USER_APPROVAL_GRANTED = "user_approval_granted"
    
    # System events
    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_ERROR = "workflow_error"
    CHANNEL_MESSAGE = "channel_message"


@dataclass
class Event:
    """Event data structure"""
    type: EventType
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    source: str = "system"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "source": self.source,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat()
        }


class EventBus:
    """
    Central event bus for decoupled communication between components.
    Singleton pattern ensures single event bus across the system.
    """
    
    _instance: Optional['EventBus'] = None
    _lock = asyncio.Lock()
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._event_history: List[Event] = []
        self._max_history = 1000  # Keep last 1000 events
        self._running = False
    
    @classmethod
    async def get(cls) -> 'EventBus':
        """Get singleton instance (async-safe)"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = EventBus()
        return cls._instance
    
    @classmethod
    def get_sync(cls) -> 'EventBus':
        """Get singleton instance (synchronous)"""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Subscribe to event type.
        
        Args:
            event_type: Type of event to subscribe to
            callback: Async function to call when event occurs
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe from event type"""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
    
    async def emit(self, event: Event):
        """
        Emit event to all subscribers.
        
        Args:
            event: Event to emit
        """
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Notify subscribers
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error in event subscriber: {e}")
    
    async def emit_async(self, event_type: EventType, data: Dict[str, Any], source: str = "system"):
        """
        Convenience method to emit event asynchronously.
        
        Args:
            event_type: Type of event
            data: Event data
            source: Source of event
        """
        event = Event(
            type=event_type,
            data=data,
            source=source
        )
        await self.emit(event)
    
    def emit_sync(self, event_type: EventType, data: Dict[str, Any], source: str = "system"):
        """
        Synchronous emit (creates event but doesn't wait for subscribers).
        
        Args:
            event_type: Type of event
            data: Event data
            source: Source of event
        """
        event = Event(
            type=event_type,
            data=data,
            source=source
        )
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)
        
        # Queue for async processing
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            print("Warning: Event queue full, dropping event")
    
    async def process_queue(self):
        """Process queued events (run in background task)"""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                await self.emit(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing event queue: {e}")
    
    def stop(self):
        """Stop event processing"""
        self._running = False
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """
        Get event history.
        
        Args:
            event_type: Filter by event type (None for all)
            limit: Maximum number of events to return
            
        Returns:
            List of events
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        return events[-limit:]
    
    def clear_history(self):
        """Clear event history"""
        self._event_history.clear()


# Convenience functions for common events

async def emit_agent_state_change(old_state: str, new_state: str, details: str = ""):
    """Emit agent state change event"""
    bus = await EventBus.get()
    await bus.emit_async(
        EventType.AGENT_STATE_CHANGE,
        {
            "old_state": old_state,
            "new_state": new_state,
            "details": details
        },
        source="lifecycle_manager"
    )


async def emit_tool_execution(tool_name: str, status: str, duration: float = 0, error: str = ""):
    """Emit tool execution event"""
    bus = await EventBus.get()
    event_type = EventType.TOOL_EXECUTION_END if status == "success" else EventType.TOOL_EXECUTION_ERROR
    
    await bus.emit_async(
        event_type,
        {
            "tool_name": tool_name,
            "status": status,
            "duration_ms": duration * 1000,
            "error": error
        },
        source="tool_executor"
    )


async def emit_memory_operation(operation: str, details: Dict[str, Any]):
    """Emit memory operation event"""
    bus = await EventBus.get()
    event_type_map = {
        "store": EventType.MEMORY_STORED,
        "retrieve": EventType.MEMORY_RETRIEVED,
        "wipe": EventType.MEMORY_WIPED
    }
    
    await bus.emit_async(
        event_type_map.get(operation, EventType.MEMORY_STORED),
        details,
        source="memory_system"
    )


async def emit_workflow_event(status: str, workflow_name: str, details: Dict[str, Any] = None):
    """Emit workflow event"""
    bus = await EventBus.get()
    event_type_map = {
        "started": EventType.WORKFLOW_STARTED,
        "completed": EventType.WORKFLOW_COMPLETED,
        "error": EventType.WORKFLOW_ERROR
    }
    
    data = {
        "workflow_name": workflow_name,
        "status": status
    }
    if details:
        data.update(details)
    
    await bus.emit_async(
        event_type_map.get(status, EventType.WORKFLOW_STARTED),
        data,
        source="workflow_engine"
    )

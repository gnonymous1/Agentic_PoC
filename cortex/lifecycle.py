"""Agent Lifecycle Manager - Inspired by PentestGPT"""

from enum import Enum
from typing import Optional
import asyncio
from cortex.events import EventBus, EventType, emit_agent_state_change


class AgentState(Enum):
    """Agent lifecycle states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    ERROR = "error"


class AgentLifecycleManager:
    """
    Manages agent lifecycle with pause/resume/inject capabilities.
    Inspired by PentestGPT's 5-state model.
    """
    
    def __init__(self):
        self._state = AgentState.IDLE
        self._pause_requested = False
        self._stop_requested = False
        self._resume_event = asyncio.Event()
        self._pending_instruction: Optional[str] = None
        self.events = EventBus.get_sync()
    
    @property
    def state(self) -> AgentState:
        """Get current agent state"""
        return self._state
    
    async def transition_to(self, new_state: AgentState, details: str = ""):
        """
        Safe state transition with event emission.
        
        Args:
            new_state: New state to transition to
            details: Optional details about the transition
        """
        old_state = self._state
        self._state = new_state
        
        await emit_agent_state_change(
            old_state=old_state.value,
            new_state=new_state.value,
            details=details
        )
        
        print(f"[STATE] {old_state.value} -> {new_state.value}")
        if details:
            print(f"   Details: {details}")
    
    def transition_to_sync(self, new_state: AgentState, details: str = ""):
        """Synchronous state transition"""
        old_state = self._state
        self._state = new_state
        
        self.events.emit_sync(
            EventType.AGENT_STATE_CHANGE,
            {
                "old_state": old_state.value,
                "new_state": new_state.value,
                "details": details
            },
            source="lifecycle_manager"
        )
        
        print(f"🔄 State: {old_state.value} → {new_state.value}")
        if details:
            print(f"   Details: {details}")
    
    async def pause(self) -> bool:
        """
        Request pause at next safe point.
        
        Returns:
            True if pause request was accepted
        """
        if self._state == AgentState.RUNNING:
            self._pause_requested = True
            await self.transition_to(AgentState.PAUSED, "User requested pause")
            return True
        return False
    
    async def resume(self, instruction: Optional[str] = None) -> bool:
        """
        Resume from paused state.
        
        Args:
            instruction: Optional instruction to inject on resume
            
        Returns:
            True if resume request was accepted
        """
        if self._state == AgentState.PAUSED:
            self._pending_instruction = instruction
            self._pause_requested = False
            self._resume_event.set()
            
            details = "Resumed"
            if instruction:
                details += f" with instruction: {instruction[:50]}..."
            
            await self.transition_to(AgentState.RUNNING, details)
            return True
        return False
    
    async def inject_instruction(self, instruction: str) -> bool:
        """
        Inject instruction at next pause point.
        
        Args:
            instruction: Instruction to inject
            
        Returns:
            True if instruction was queued
        """
        if self._state in (AgentState.RUNNING, AgentState.PAUSED):
            self._pending_instruction = instruction
            print(f"[INJECT] Instruction queued: {instruction[:50]}...")
            return True
        return False
    
    async def stop(self) -> bool:
        """
        Request stop.
        
        Returns:
            True (stop is always accepted)
        """
        self._stop_requested = True
        self._resume_event.set()  # Unblock if paused
        await self.transition_to(AgentState.COMPLETED, "User requested stop")
        return True
    
    async def check_pause_point(self):
        """
        Check if pause requested and wait if needed.
        Call this at safe points during execution.
        """
        if self._pause_requested:
            await self.transition_to(AgentState.PAUSED, "Reached safe pause point")
            await self._resume_event.wait()
            self._resume_event.clear()
    
    def is_stop_requested(self) -> bool:
        """Check if stop was requested"""
        return self._stop_requested
    
    def get_pending_instruction(self) -> Optional[str]:
        """Get and clear pending instruction"""
        instruction = self._pending_instruction
        self._pending_instruction = None
        return instruction
    
    async def error(self, error_message: str):
        """Transition to error state"""
        await self.transition_to(AgentState.ERROR, error_message)
        
        # Emit error event
        await self.events.emit_async(
            EventType.AGENT_ERROR,
            {
                "error": error_message,
                "state": self._state.value
            },
            source="lifecycle_manager"
        )
    
    def reset(self):
        """Reset lifecycle manager to idle state"""
        self._state = AgentState.IDLE
        self._pause_requested = False
        self._stop_requested = False
        self._pending_instruction = None
        if self._resume_event.is_set():
            self._resume_event.clear()


# Global lifecycle manager instance
_lifecycle_manager: Optional[AgentLifecycleManager] = None


def get_lifecycle_manager() -> AgentLifecycleManager:
    """Get global lifecycle manager instance"""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = AgentLifecycleManager()
    return _lifecycle_manager

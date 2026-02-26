"""
Agent Bridge - Connect channels to agent graph
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage

from cortex.graph import graph
from cortex.events import EventBus, EventType


class AgentBridge:
    """
    Bridge between messaging channels and agent graph.
    Routes messages from channels to agents and formats responses back to channels.
    """
    
    def __init__(self):
        self.event_bus = EventBus.get_sync()
        
        # Context storage: session_id -> conversation context
        self.contexts: Dict[str, Dict[str, Any]] = {}
        
        # Channel references: channel_id -> channel instance
        self.channels: Dict[str, Any] = {}
    
    def register_channel(self, channel_id: str, channel: Any):
        """
        Register a channel with the bridge.
        
        Args:
            channel_id: Channel identifier
            channel: Channel instance
        """
        self.channels[channel_id] = channel
        
        # Subscribe to channel messages
        channel.on_message(lambda msg: asyncio.create_task(self.route_to_agent(channel_id, msg)))
        
        print(f"[AgentBridge] Channel registered: {channel_id}")
    
    async def route_to_agent(self, channel_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route message from channel to agent graph.
        
        Args:
            channel_id: Source channel ID
            message: Message data
            
        Returns:
            Agent response
        """
        try:
            # Extract message details
            sender = message.get("from", "unknown")
            content = message.get("content", "")
            
            print(f"[AgentBridge] Routing message from {channel_id}/{sender}: {content[:50]}...")
            
            # Get or create context
            context_key = f"{channel_id}:{sender}"
            if context_key not in self.contexts:
                self.contexts[context_key] = {
                    "messages": [],
                    "blackboard": {},
                    "plan": None,
                    "meta_data": {
                        "channel": channel_id,
                        "user": sender
                    }
                }
            
            context = self.contexts[context_key]
            
            # Add user message to context
            context["messages"].append(HumanMessage(content=content))
            
            # Emit routing event
            self.event_bus.emit_sync(
                EventType.CHANNEL_MESSAGE,
                {
                    "action": "routing_to_agent",
                    "channel": channel_id,
                    "sender": sender,
                    "content_preview": content[:100]
                },
                source="agent_bridge"
            )
            
            # Execute agent graph
            response_content = ""
            async for event in graph.astream(context):
                for node_name, node_state in event.items():
                    print(f"[AgentBridge] Agent node: {node_name}")
                    
                    # Extract response from messages
                    if "messages" in node_state and len(node_state["messages"]) > 0:
                        last_message = node_state["messages"][-1]
                        if hasattr(last_message, "content"):
                            response_content = last_message.content
            
            # Update context with agent response
            if response_content:
                context["messages"].append(AIMessage(content=response_content))
            
            # Format response for channel
            formatted_response = await self.format_for_channel(channel_id, {
                "content": response_content,
                "sender": sender
            })
            
            # Send response back through channel
            await self.send_to_channel(channel_id, sender, formatted_response)
            
            # Emit completion event
            self.event_bus.emit_sync(
                EventType.AGENT_COMPLETED,
                {
                    "channel": channel_id,
                    "sender": sender,
                    "response_length": len(response_content)
                },
                source="agent_bridge"
            )
            
            return {
                "content": response_content,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            print(f"[AgentBridge] Error routing to agent: {e}")
            
            # Emit error event
            self.event_bus.emit_sync(
                EventType.AGENT_ERROR,
                {
                    "error": str(e),
                    "channel": channel_id,
                    "sender": message.get("from", "unknown")
                },
                source="agent_bridge"
            )
            
            # Send error message to channel
            error_message = "Sorry, I encountered an error processing your request. Please try again."
            await self.send_to_channel(channel_id, message.get("from"), error_message)
            
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def format_for_channel(self, channel_id: str, response: Dict[str, Any]) -> str:
        """
        Format agent response for specific channel.
        
        Args:
            channel_id: Target channel ID
            response: Agent response data
            
        Returns:
            Formatted message string
        """
        content = response.get("content", "")
        
        # Channel-specific formatting
        if channel_id == "telegram":
            # Telegram supports Markdown
            # Could add formatting here if needed
            return content
        
        elif channel_id == "web":
            # Web channel supports HTML/Markdown
            return content
        
        else:
            # Default: plain text
            return content
    
    async def send_to_channel(self, channel_id: str, recipient: str, message: str) -> bool:
        """
        Send message through specific channel.
        
        Args:
            channel_id: Channel ID
            recipient: Recipient identifier
            message: Message content
            
        Returns:
            True if sent successfully
        """
        if channel_id in self.channels:
            channel = self.channels[channel_id]
            return await channel.send_message(recipient, message)
        else:
            print(f"[AgentBridge] Channel not found: {channel_id}")
            return False
    
    def preserve_context(self, session_id: str, context: Dict[str, Any]):
        """
        Manually preserve context for session.
        
        Args:
            session_id: Session identifier
            context: Context data to preserve
        """
        self.contexts[session_id] = context
    
    def get_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get context for session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context data if exists, None otherwise
        """
        return self.contexts.get(session_id)
    
    def clear_context(self, session_id: str):
        """
        Clear context for session.
        
        Args:
            session_id: Session identifier
        """
        if session_id in self.contexts:
            del self.contexts[session_id]
            print(f"[AgentBridge] Context cleared for {session_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get bridge statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "registered_channels": len(self.channels),
            "active_contexts": len(self.contexts),
            "channels": list(self.channels.keys())
        }


# Global bridge instance
_bridge_instance: Optional[AgentBridge] = None


def get_agent_bridge() -> AgentBridge:
    """Get global AgentBridge instance"""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = AgentBridge()
    return _bridge_instance

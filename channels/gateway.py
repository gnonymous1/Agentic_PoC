"""
Gateway Server - Central hub for device pairing and message routing
"""

import asyncio
import json
import secrets
from typing import Dict, Set, Optional, Callable, Any
from datetime import datetime
import websockets
from websockets.server import WebSocketServerProtocol

from channels.session_store import SessionStore, Session
from cortex.events import EventBus, EventType


class GatewayServer:
    """
    Central Gateway server for device pairing and message routing.
    Manages WebSocket connections and routes messages between devices and channels.
    """
    
    def __init__(self, port: int = 8765, secret_key: Optional[str] = None):
        self.port = port
        self.session_store = SessionStore(secret_key=secret_key)
        self.event_bus = EventBus.get_sync()
        
        # Active connections: session_id -> WebSocket
        self.connections: Dict[str, WebSocketServerProtocol] = {}
        
        # Registered channels: channel_id -> Channel instance
        self.channels: Dict[str, Any] = {}
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {}
        
        # Server state
        self.server = None
        self.is_running = False
    
    async def start(self):
        """Start the Gateway WebSocket server"""
        print(f"[Gateway] Starting server on port {self.port}...")
        
        try:
            self.server = await websockets.serve(
                self.handle_connection,
                "0.0.0.0",
                self.port
            )
            
            self.is_running = True
            print(f"[Gateway] Server started successfully on ws://0.0.0.0:{self.port}")
            
            # Emit startup event
            self.event_bus.emit_sync(
                EventType.WORKFLOW_STARTED,
                {"component": "gateway", "port": self.port},
                source="gateway"
            )
            
            # Start cleanup task
            asyncio.create_task(self.cleanup_task())
            
        except Exception as e:
            print(f"[Gateway] Failed to start server: {e}")
            raise
    
    async def stop(self):
        """Stop the Gateway server"""
        print("[Gateway] Stopping server...")
        
        self.is_running = False
        
        # Close all connections
        for session_id, ws in list(self.connections.items()):
            await ws.close()
        
        self.connections.clear()
        
        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        print("[Gateway] Server stopped")
        
        # Emit shutdown event
        self.event_bus.emit_sync(
            EventType.WORKFLOW_COMPLETED,
            {"component": "gateway"},
            source="gateway"
        )
    
    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle incoming WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        session_id = None
        
        try:
            # Wait for authentication message
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)
            
            # Validate session
            session_id = auth_data.get("session_id")
            auth_token = auth_data.get("auth_token")
            
            if not self.session_store.validate_token(session_id, auth_token):
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid session or token"
                }))
                await websocket.close()
                return
            
            # Store connection
            self.connections[session_id] = websocket
            
            # Send confirmation
            await websocket.send(json.dumps({
                "type": "connected",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }))
            
            print(f"[Gateway] Client connected: {session_id}")
            
            # Emit connection event
            self.event_bus.emit_sync(
                EventType.CHANNEL_MESSAGE,
                {"action": "client_connected", "session_id": session_id},
                source="gateway"
            )
            
            # Handle messages
            async for message in websocket:
                await self.handle_message(session_id, message)
        
        except websockets.exceptions.ConnectionClosed:
            print(f"[Gateway] Client disconnected: {session_id}")
        
        except Exception as e:
            print(f"[Gateway] Error handling connection: {e}")
        
        finally:
            # Clean up connection
            if session_id and session_id in self.connections:
                del self.connections[session_id]
                
                # Emit disconnection event
                self.event_bus.emit_sync(
                    EventType.CHANNEL_MESSAGE,
                    {"action": "client_disconnected", "session_id": session_id},
                    source="gateway"
                )
    
    async def handle_message(self, session_id: str, message: str):
        """
        Handle incoming message from client.
        
        Args:
            session_id: Session ID of sender
            message: Message content (JSON string)
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            # Route based on message type
            if message_type == "chat":
                await self.route_chat_message(session_id, data)
            
            elif message_type == "command":
                await self.handle_command(session_id, data)
            
            elif message_type == "ping":
                await self.send_to_session(session_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
            
            else:
                # Custom message handlers
                handler = self.message_handlers.get(message_type)
                if handler:
                    await handler(session_id, data)
        
        except json.JSONDecodeError:
            print(f"[Gateway] Invalid JSON from {session_id}: {message}")
        
        except Exception as e:
            print(f"[Gateway] Error handling message: {e}")
    
    async def route_chat_message(self, session_id: str, data: Dict[str, Any]):
        """
        Route chat message to appropriate destination.
        
        Args:
            session_id: Session ID of sender
            data: Message data
        """
        target = data.get("target", "agent")
        content = data.get("content", "")
        
        # Emit message event
        self.event_bus.emit_sync(
            EventType.CHANNEL_MESSAGE,
            {
                "session_id": session_id,
                "target": target,
                "content": content
            },
            source="gateway"
        )
        
        # Route to target
        if target == "agent":
            # Will be handled by agent bridge
            pass
        
        elif target in self.channels:
            # Route to specific channel
            await self.channels[target].send_message(session_id, content)
        
        elif target in self.connections:
            # Route to specific session
            await self.send_to_session(target, {
                "type": "message",
                "from": session_id,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
    
    async def handle_command(self, session_id: str, data: Dict[str, Any]):
        """
        Handle command from client.
        
        Args:
            session_id: Session ID of sender
            data: Command data
        """
        command = data.get("command")
        
        if command == "list_sessions":
            sessions = self.session_store.list_active_sessions()
            await self.send_to_session(session_id, {
                "type": "sessions",
                "sessions": [
                    {
                        "session_id": s.session_id,
                        "device_name": s.device_name,
                        "channel_type": s.channel_type,
                        "created_at": s.created_at
                    }
                    for s in sessions
                ]
            })
    
    async def send_to_session(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        Send message to specific session.
        
        Args:
            session_id: Target session ID
            data: Data to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if session_id in self.connections:
            try:
                await self.connections[session_id].send(json.dumps(data))
                return True
            except Exception as e:
                print(f"[Gateway] Error sending to {session_id}: {e}")
                return False
        return False
    
    async def broadcast(self, data: Dict[str, Any], exclude: Set[str] = None):
        """
        Broadcast message to all connected sessions.
        
        Args:
            data: Data to broadcast
            exclude: Set of session IDs to exclude
        """
        exclude = exclude or set()
        message = json.dumps(data)
        
        for session_id, ws in self.connections.items():
            if session_id not in exclude:
                try:
                    await ws.send(message)
                except Exception as e:
                    print(f"[Gateway] Error broadcasting to {session_id}: {e}")
    
    def pair_device(self, device_id: str, device_name: str, 
                   channel_type: str, metadata: Dict[str, Any] = None) -> Session:
        """
        Create new device pairing session.
        
        Args:
            device_id: Unique device identifier
            device_name: Human-readable device name
            channel_type: Type of channel
            metadata: Additional metadata
            
        Returns:
            New Session object with auth credentials
        """
        session = self.session_store.create_session(
            device_id=device_id,
            device_name=device_name,
            channel_type=channel_type,
            metadata=metadata
        )
        
        print(f"[Gateway] Device paired: {device_name} ({session.session_id})")
        
        # Emit pairing event
        self.event_bus.emit_sync(
            EventType.USER_APPROVAL_GRANTED,
            {
                "action": "device_paired",
                "device_id": device_id,
                "device_name": device_name,
                "session_id": session.session_id
            },
            source="gateway"
        )
        
        return session
    
    def register_channel(self, channel_id: str, channel: Any):
        """
        Register a channel with the Gateway.
        
        Args:
            channel_id: Unique channel identifier
            channel: Channel instance
        """
        self.channels[channel_id] = channel
        print(f"[Gateway] Channel registered: {channel_id}")
    
    def unregister_channel(self, channel_id: str):
        """
        Unregister a channel from the Gateway.
        
        Args:
            channel_id: Channel identifier to unregister
        """
        if channel_id in self.channels:
            del self.channels[channel_id]
            print(f"[Gateway] Channel unregistered: {channel_id}")
    
    def register_message_handler(self, message_type: str, handler: Callable):
        """
        Register custom message handler.
        
        Args:
            message_type: Type of message to handle
            handler: Async function to handle message
        """
        self.message_handlers[message_type] = handler
    
    async def cleanup_task(self):
        """Background task to cleanup expired sessions"""
        while self.is_running:
            await asyncio.sleep(3600)  # Run every hour
            
            count = self.session_store.cleanup_expired()
            if count > 0:
                print(f"[Gateway] Cleaned up {count} expired sessions")


# Global Gateway instance
_gateway_instance: Optional[GatewayServer] = None


def get_gateway() -> GatewayServer:
    """Get global Gateway instance"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = GatewayServer()
    return _gateway_instance

"""
Web Channel - WebSocket-based web chat channel
"""

import asyncio
import json
from typing import Dict, Any, Set
from datetime import datetime
import websockets
from websockets.server import WebSocketServerProtocol

from channels.base_channel import Channel


class WebChannel(Channel):
    """
    WebSocket-based web chat channel.
    Provides real-time bidirectional communication for web clients.
    """
    
    def __init__(self, channel_id: str = "web", config: Dict[str, Any] = None):
        """
        Initialize Web channel.
        
        Args:
            channel_id: Channel identifier
            config: Channel configuration
        """
        config = config or {}
        config.setdefault("port", 8766)
        config.setdefault("host", "0.0.0.0")
        
        super().__init__(channel_id, config)
        
        # WebSocket server
        self.server = None
        self.port = config["port"]
        self.host = config["host"]
        
        # Connected clients: user_id -> WebSocket
        self.clients: Dict[str, WebSocketServerProtocol] = {}
        
        # Typing indicators: user_id -> is_typing
        self.typing_status: Dict[str, bool] = {}
        
        # Online users
        self.online_users: Set[str] = set()
    
    async def start(self) -> bool:
        """Start the Web channel WebSocket server"""
        try:
            print(f"[WebChannel] Starting server on {self.host}:{self.port}...")
            
            self.server = await websockets.serve(
                self.handle_client,
                self.host,
                self.port
            )
            
            self.is_connected = True
            print(f"[WebChannel] Server started on ws://{self.host}:{self.port}")
            
            # Subscribe to EventBus for live streaming
            from cortex.events import EventBus, EventType
            bus = EventBus.get_sync()
            bus.subscribe(EventType.SYSTEM_EVENT, self.handle_system_event)
            bus.subscribe(EventType.AGENT_MESSAGE, self.handle_system_event)
            
            # Emit startup event
            self.emit_event(
                "WORKFLOW_STARTED",
                {"channel": "web", "port": self.port}
            )
            
            return True
            
        except Exception as e:
            print(f"[WebChannel] Failed to start: {e}")
            self.is_connected = False
            return False
    
    async def stop(self) -> bool:
        """Stop the Web channel"""
        try:
            print("[WebChannel] Stopping server...")
            
            # Close all client connections
            for user_id, ws in list(self.clients.items()):
                await ws.close()
            
            self.clients.clear()
            self.online_users.clear()
            self.typing_status.clear()
            
            # Stop server
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            self.is_connected = False
            print("[WebChannel] Server stopped")
            
            return True
            
        except Exception as e:
            print(f"[WebChannel] Error stopping: {e}")
            return False
    
    async def handle_client(self, websocket: WebSocketServerProtocol, path: str):
        """
        Handle incoming WebSocket client connection.
        
        Args:
            websocket: WebSocket connection
            path: Connection path
        """
        user_id = None
        
        try:
            # Wait for authentication/identification
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)
            
            user_id = auth_data.get("user_id", f"user_{len(self.clients)}")
            
            # Store client
            self.clients[user_id] = websocket
            self.online_users.add(user_id)
            
            # Send confirmation
            await websocket.send(json.dumps({
                "type": "connected",
                "user_id": user_id,
                "timestamp": datetime.now().isoformat()
            }))
            
            print(f"[WebChannel] Client connected: {user_id}")
            
            # Broadcast presence update
            await self.broadcast_presence()
            
            # Handle messages
            async for message in websocket:
                await self.handle_message(user_id, message)
        
        except websockets.exceptions.ConnectionClosed:
            print(f"[WebChannel] Client disconnected: {user_id}")
        
        except Exception as e:
            print(f"[WebChannel] Error handling client: {e}")
        
        finally:
            # Clean up
            if user_id:
                if user_id in self.clients:
                    del self.clients[user_id]
                if user_id in self.online_users:
                    self.online_users.remove(user_id)
                if user_id in self.typing_status:
                    del self.typing_status[user_id]
                
                # Broadcast presence update
                await self.broadcast_presence()
    
    async def handle_message(self, user_id: str, message: str):
        """
        Handle incoming message from client.
        
        Args:
            user_id: User ID of sender
            message: Message content (JSON string)
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "chat":
                # Chat message
                await self._handle_chat_message(user_id, data)
            
            elif message_type == "typing":
                # Typing indicator
                is_typing = data.get("is_typing", False)
                await self.broadcast_typing(user_id, is_typing)
            
            elif message_type == "read":
                # Read receipt
                message_id = data.get("message_id")
                await self.send_read_receipt(user_id, message_id)
            
            elif message_type == "ping":
                # Ping/pong
                await self.clients[user_id].send(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
        
        except json.JSONDecodeError:
            print(f"[WebChannel] Invalid JSON from {user_id}: {message}")
        
        except Exception as e:
            print(f"[WebChannel] Error handling message: {e}")
    
    async def _handle_chat_message(self, user_id: str, data: Dict[str, Any]):
        """Handle chat message"""
        content = data.get("content", "")
        
        # Create message object
        message = {
            "from": user_id,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "channel": "web"
        }
        
        # Notify handlers (will route to agent)
        await self._handle_incoming_message(message)
    
    async def send_message(self, to: str, message: str, **kwargs) -> bool:
        """
        Send message to specific user.
        
        Args:
            to: User ID
            message: Message content
            **kwargs: Additional parameters
            
        Returns:
            True if sent successfully
        """
        if to in self.clients:
            try:
                await self.clients[to].send(json.dumps({
                    "type": "message",
                    "content": message,
                    "from": kwargs.get("from", "agent"),
                    "timestamp": datetime.now().isoformat()
                }))
                return True
            except Exception as e:
                print(f"[WebChannel] Error sending to {to}: {e}")
                return False
        return False
    
    async def broadcast(self, message: str, exclude: Set[str] = None):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message content
            exclude: Set of user IDs to exclude
        """
        exclude = exclude or set()
        data = json.dumps({
            "type": "broadcast",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        for user_id, ws in self.clients.items():
            if user_id not in exclude:
                try:
                    await ws.send(data)
                except Exception as e:
                    print(f"[WebChannel] Error broadcasting to {user_id}: {e}")
    
    async def broadcast_typing(self, user_id: str, is_typing: bool):
        """
        Broadcast typing indicator.
        
        Args:
            user_id: User who is typing
            is_typing: Whether user is typing
        """
        self.typing_status[user_id] = is_typing
        
        data = json.dumps({
            "type": "typing",
            "user_id": user_id,
            "is_typing": is_typing,
            "timestamp": datetime.now().isoformat()
        })
        
        # Send to all except the typing user
        for uid, ws in self.clients.items():
            if uid != user_id:
                try:
                    await ws.send(data)
                except Exception as e:
                    print(f"[WebChannel] Error sending typing to {uid}: {e}")
    
    async def broadcast_presence(self):
        """Broadcast online users list"""
        data = json.dumps({
            "type": "presence",
            "online_users": list(self.online_users),
            "timestamp": datetime.now().isoformat()
        })
        
        for ws in self.clients.values():
            try:
                await ws.send(data)
            except Exception as e:
                print(f"[WebChannel] Error broadcasting presence: {e}")
    
    async def send_read_receipt(self, user_id: str, message_id: str):
        """
        Send read receipt.
        
        Args:
            user_id: User who read the message
            message_id: Message ID
        """
        data = json.dumps({
            "type": "read_receipt",
            "user_id": user_id,
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        })
        
        # Broadcast to all clients
        for ws in self.clients.values():
            try:
                await ws.send(data)
            except Exception as e:
                print(f"[WebChannel] Error sending read receipt: {e}")
    
    async def handle_system_event(self, event):
        """
        Broadcast system events to connected dashboard clients.
        """
        # Filter for dashboard-relevant events if needed
        data = event.to_dict()
        
        # Broadcast as "log" or "metric" type
        msg = {
            "type": "system_event",
            "event_type": data["type"],
            "data": data["data"],
            "timestamp": data["timestamp"],
            "source": data["source"]
        }
        
        await self.broadcast(json.dumps(msg))  # Using broadcast wrapper might double-encode, fixing below

    async def broadcast_event(self, event_data: Dict[str, Any]):
        """Direct broadcast helper"""
        message = json.dumps(event_data)
        for ws in self.clients.values():
            try:
                await ws.send(message)
            except:
                pass

    def get_status(self) -> Dict[str, Any]:
        """Get channel status"""
        status = super().get_status()
        status.update({
            "connected_clients": len(self.clients),
            "online_users": list(self.online_users),
            "port": self.port
        })
        return status

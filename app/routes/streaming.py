"""
WebSocket streaming endpoints for real-time agent communication and LiveKit transport.
"""

import json
import logging
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.agents.voice_agent import VoiceProxyAgent
from app.core.orchestrator import AgentContext, DAGOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Streaming"])


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[client_id] = ws

    def disconnect(self, client_id: str):
        self._connections.pop(client_id, None)

    async def send(self, client_id: str, message: dict):
        ws = self._connections.get(client_id)
        if ws:
            await ws.send_json(message)

    async def send_bytes(self, client_id: str, data: bytes):
        ws = self._connections.get(client_id)
        if ws:
            await ws.send_bytes(data)

    async def broadcast(self, message: dict):
        for ws in self._connections.values():
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/live/{client_id}")
async def agent_stream(ws: WebSocket, client_id: str):
    await manager.connect(client_id, ws)
    session_id = str(uuid4())

    orchestrator = DAGOrchestrator()
    voice_agent = VoiceProxyAgent()
    orchestrator.register(voice_agent)

    ctx = AgentContext(
        topic="voice_session",
        metadata={
            "session_id": session_id,
            "client_id": client_id,
        },
    )

    try:
        ctx = await orchestrator.run(ctx)

        livekit_token = ctx.metadata.get("livekit_token")
        room_name = ctx.metadata.get("livekit_room")
        recall_session_id = ctx.metadata.get("recall_session_id")

        await manager.send(client_id, {
            "type": "session_started",
            "payload": {
                "session_id": session_id,
                "livekit_token": livekit_token,
                "livekit_room": room_name,
                "recall_session_id": recall_session_id,
            },
        })

        while True:
            data = await ws.receive_json()
            await manager.send(client_id, {
                "type": "ack",
                "payload": {"received": data.get("type", "unknown")},
            })
    except WebSocketDisconnect:
        logger.info("Client %s disconnected from live session %s", client_id, session_id)
    except Exception as exc:
        logger.error("Live session %s failed for client %s: %s", session_id, client_id, exc)
        try:
            await manager.send(client_id, {
                "type": "error",
                "payload": {"message": str(exc)},
            })
        except Exception:
            pass
    finally:
        manager.disconnect(client_id)


@router.websocket("/ws/audio/{session_id}")
async def audio_stream(ws: WebSocket, session_id: str):
    """Bi-directional binary audio streaming for voice proxy."""
    await ws.accept()
    logger.info("Audio stream opened for session %s", session_id)
    try:
        while True:
            message = await ws.receive()
            if message["type"] == "websocket.receive" and message.get("bytes"):
                await ws.send_bytes(message["bytes"])
            elif message["type"] == "websocket.receive" and message.get("text"):
                text_data = json.loads(message["text"])
                await ws.send_json({
                    "type": "audio_ack",
                    "payload": {"session_id": session_id},
                })
    except WebSocketDisconnect:
        logger.info("Audio stream closed for session %s", session_id)

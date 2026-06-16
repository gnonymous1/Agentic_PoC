"""
GNONE — Voice Agent.
LiveKit WebRTC + Gemini Live voice proxy for meeting attendance.
"""

import os
import json
import base64
import logging
import asyncio
from typing import Dict, Any, Optional, List

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class VoiceAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "voice_agent"

    @property
    def description(self) -> str:
        return "Real-time voice proxy via LiveKit WebRTC and Gemini Live API"

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.livekit_url = os.getenv("LIVEKIT_HOST", "")
        self.is_speaking = False
        self.audio_buffer: List[bytes] = []
        self.interruption_event = asyncio.Event()

    async def execute(self, meeting_url: str, agent_prompt: str, voice_model: str = "Puck", **kwargs) -> Dict[str, Any]:
        logger.info("VoiceAgent: Joining meeting %s", meeting_url)
        return {
            "status": "connected",
            "meeting_url": meeting_url,
            "voice_model": voice_model,
            "message": "Voice proxy active. Use connect_livekit_session() and start_session_loop() for full WebRTC.",
        }

    async def trigger_interruption(self) -> None:
        """VAD-triggered audio cancellation."""
        if self.is_speaking:
            logger.warning("VAD: Human interruption detected")
            self.interruption_event.set()
            self.audio_buffer.clear()
            self.is_speaking = False

"""
LiveKit WebRTC orchestration service.
Manages real-time audio/video matrix for agent participation in meetings.
"""

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LiveKitRoom:
    room_name: str
    room_sid: str
    participant_count: int = 0


class LiveKitService:
    """
    LiveKit Server integration for bi-directional audio/video streaming.
    Handles room creation, participant management, and track publishing.
    """

    def __init__(self):
        self._api_key = settings.livekit_api_key
        self._api_secret = settings.livekit_api_secret
        self._host = settings.livekit_host
        self._import_error: str | None = None

    async def create_room(self, room_name: str) -> LiveKitRoom:
        try:
            from livekit import api
        except ImportError as exc:
            msg = "livekit package not installed (install with: pip install 'gnone[livekit]')"
            self._import_error = str(exc)
            logger.error(msg)
            raise RuntimeError(msg) from exc

        lkapi = api.LiveKitAPI(self._host, self._api_key, self._api_secret)
        try:
            room = await lkapi.room.create_room(
                api.CreateRoomRequest(name=room_name)
            )
            return LiveKitRoom(
                room_name=room.name,
                room_sid=room.sid,
            )
        except Exception as exc:
            logger.error("Failed to create LiveKit room '%s': %s", room_name, exc)
            raise

    async def generate_token(
        self,
        room_name: str,
        identity: str,
        ttl_seconds: int = 300,
    ) -> str:
        try:
            from livekit import api
        except ImportError as exc:
            msg = "livekit package not installed (install with: pip install 'gnone[livekit]')"
            self._import_error = str(exc)
            logger.error(msg)
            raise RuntimeError(msg) from exc

        try:
            token = api.AccessToken(self._api_key, self._api_secret) \
                .with_identity(identity) \
                .with_name(f"GNONE Agent - {identity}") \
                .with_grants(api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                ))
            return token.to_jwt()
        except Exception as exc:
            logger.error("Failed to generate token for '%s' in room '%s': %s", identity, room_name, exc)
            raise

    async def close_room(self, room_name: str):
        try:
            from livekit import api
        except ImportError as exc:
            msg = "livekit package not installed (install with: pip install 'gnone[livekit]')"
            self._import_error = str(exc)
            logger.error(msg)
            raise RuntimeError(msg) from exc

        lkapi = api.LiveKitAPI(self._host, self._api_key, self._api_secret)
        try:
            await lkapi.room.delete_room(
                api.DeleteRoomRequest(room=room_name)
            )
            logger.info("LiveKit room '%s' closed", room_name)
        except Exception as exc:
            logger.error("Failed to close LiveKit room '%s': %s", room_name, exc)
            raise

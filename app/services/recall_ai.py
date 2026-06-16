"""
Recall.ai container management service.
Spawns isolated headless Chromium containers for entering Zoom/Meet/Teams sessions.
"""

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RecallSessionConfig:
    meeting_url: str
    platform: str = "zoom"
    recording_mode: str = "audio_video"
    resolution: str = "1920x1080"
    duration_minutes: int = 60


@dataclass
class RecallSession:
    session_id: str
    status: str
    meeting_url: str
    platform: str
    recording_url: str | None = None


class RecallAIService:
    """
    Recall.ai integration for automated meeting container management.
    Spawns a hardware-accelerated headless Chromium to negotiate meeting entry.
    """

    def __init__(self):
        self._api_key = settings.recall_ai_api_key
        self._base_url = settings.recall_ai_base_url

    async def create_session(self, config: RecallSessionConfig) -> RecallSession:
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._base_url}/bot",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "meeting_url": config.meeting_url,
                        "platform": config.platform,
                        "recording_mode": config.recording_mode,
                        "resolution": config.resolution,
                        "duration": config.duration_minutes,
                    },
                )
                response.raise_for_status()
                data = response.json()
                logger.info("Recall.ai session created: id=%s status=%s", data["id"], data["status"])
                return RecallSession(
                    session_id=data["id"],
                    status=data["status"],
                    meeting_url=config.meeting_url,
                    platform=config.platform,
                )
            except httpx.HTTPStatusError as exc:
                logger.error("Recall.ai API error creating session: %s - %s", exc.response.status_code, exc.response.text)
                raise
            except Exception as exc:
                logger.error("Recall.ai session creation failed: %s", exc)
                raise

    async def get_transcript(self, session_id: str) -> str | None:
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self._base_url}/bot/{session_id}/transcript",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if response.status_code == 404:
                    logger.info("No transcript found for session %s", session_id)
                    return None
                response.raise_for_status()
                data = response.json()
                transcript = data.get("transcript", {}).get("full_transcript")
                logger.info("Transcript retrieved for session %s", session_id)
                return transcript
            except Exception as exc:
                logger.error("Failed to get transcript for session %s: %s", session_id, exc)
                raise

    async def stop_session(self, session_id: str) -> bool:
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self._base_url}/bot/{session_id}/stop",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                success = response.status_code == 200
                logger.info("Recall.ai session %s stopped: %s", session_id, "ok" if success else "failed")
                return success
            except Exception as exc:
                logger.error("Failed to stop Recall.ai session %s: %s", session_id, exc)
                raise

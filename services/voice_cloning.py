"""
Async voice cloning gateway for ElevenLabs and Cartesia APIs.
Handles sample upload, training trigger, status polling, and model ID persistence.
"""

import asyncio
import json
import logging
import os
from enum import Enum
from typing import Optional
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class VoiceProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    CARTESIA = "cartesia"


class CloneStatus(str, Enum):
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    TRAINING = "TRAINING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"


ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
CARTESIA_BASE = "https://api.cartesia.ai/v1"

_MAX_POLL_RETRIES = 60
_POLL_INTERVAL_SECONDS = 5


def _get_elevenlabs_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY", "")
    if not key:
        logger.warning("ELEVENLABS_API_KEY not set — voice cloning will fail")
    return key


def _get_cartesia_key() -> str:
    key = os.getenv("CARTESIA_API_KEY", "")
    if not key:
        logger.warning("CARTESIA_API_KEY not set — voice cloning will fail")
    return key


async def upload_voice_sample_elevenlabs(
    file_path: str,
    voice_name: str,
    description: str = "",
) -> dict:
    """
    Upload a WAV file to ElevenLabs for voice cloning.
    Returns the voice_id if successful.
    """
    api_key = _get_elevenlabs_key()
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")

    url = f"{ELEVENLABS_BASE}/voices/add"
    headers = {"xi-api-key": api_key}

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Voice sample not found: {file_path}")

    with open(file_path, "rb") as f:
        files = {
            "files": (os.path.basename(file_path), f, "audio/wav"),
        }
        data = {
            "name": voice_name,
            "description": description or f"Clone voice: {voice_name}",
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
            resp.raise_for_status()
            result = resp.json()

    voice_id = result.get("voice_id")
    logger.info(
        "ElevenLabs voice upload complete — name=%s voice_id=%s",
        voice_name, voice_id,
    )
    return result


async def upload_voice_sample_cartesia(
    file_path: str,
    voice_name: str,
) -> dict:
    """Upload voice sample to Cartesia for cloning."""
    api_key = _get_cartesia_key()
    if not api_key:
        raise RuntimeError("CARTESIA_API_KEY is not configured")

    url = f"{CARTESIA_BASE}/voices/clone"
    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Voice sample not found: {file_path}")

    import base64
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "name": voice_name,
        "audio": encoded,
        "audio_format": "wav",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()

    logger.info(
        "Cartesia voice upload complete — name=%s id=%s",
        voice_name, result.get("id"),
    )
    return result


async def poll_elevenlabs_voice_status(
    voice_id: str,
    max_retries: int = _MAX_POLL_RETRIES,
    interval: float = _POLL_INTERVAL_SECONDS,
) -> str:
    """
    Poll ElevenLabs until the voice clone is ready or fails.
    Returns 'ACTIVE' or raises RuntimeError.
    """
    api_key = _get_elevenlabs_key()
    url = f"{ELEVENLABS_BASE}/voices/{voice_id}"
    headers = {"xi-api-key": api_key}

    for attempt in range(1, max_retries + 1):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "unknown")
        if status == "active":
            logger.info("ElevenLabs voice %s is ACTIVE (attempt %d)", voice_id, attempt)
            return "ACTIVE"
        if status in ("failed", "error"):
            raise RuntimeError(
                f"ElevenLabs voice cloning failed for {voice_id}: {data.get('error', 'unknown')}"
            )

        logger.debug(
            "Polling ElevenLabs voice %s — status=%s attempt=%d/%d",
            voice_id, status, attempt, max_retries,
        )
        await asyncio.sleep(interval)

    raise RuntimeError(
        f"ElevenLabs voice {voice_id} did not become active after {max_retries} polls"
    )


async def poll_cartesia_voice_status(
    voice_id: str,
    max_retries: int = _MAX_POLL_RETRIES,
    interval: float = _POLL_INTERVAL_SECONDS,
) -> str:
    """Poll Cartesia until voice clone is ready."""
    api_key = _get_cartesia_key()
    url = f"{CARTESIA_BASE}/voices/{voice_id}"
    headers = {"X-API-Key": api_key}

    for attempt in range(1, max_retries + 1):
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        status = data.get("status", "unknown")
        if status == "active":
            logger.info("Cartesia voice %s is ACTIVE (attempt %d)", voice_id, attempt)
            return "ACTIVE"
        if status in ("failed", "error"):
            raise RuntimeError(
                f"Cartesia voice cloning failed for {voice_id}: {data.get('error', 'unknown')}"
            )

        await asyncio.sleep(interval)

    raise RuntimeError(
        f"Cartesia voice {voice_id} did not become active after {max_retries} polls"
    )


async def clone_voice(
    file_path: str,
    voice_name: str,
    provider: VoiceProvider = VoiceProvider.ELEVENLABS,
    db_session: Optional[AsyncSession] = None,
    client_id: Optional[UUID] = None,
    agent_profile_id: Optional[UUID] = None,
) -> dict:
    """
    Full voice cloning workflow:
    1. Upload sample
    2. Poll until active
    3. Persist voice_model_id to DB
    Returns dict with voice_model_id and status.
    """
    from database.models import VoiceCloneJob as VoiceCloneJobModel

    try:
        if provider == VoiceProvider.ELEVENLABS:
            upload_result = await upload_voice_sample_elevenlabs(file_path, voice_name)
            provider_job_id = upload_result.get("voice_id")
            await poll_elevenlabs_voice_status(provider_job_id)
            voice_model_id = provider_job_id
        elif provider == VoiceProvider.CARTESIA:
            upload_result = await upload_voice_sample_cartesia(file_path, voice_name)
            provider_job_id = upload_result.get("id")
            await poll_cartesia_voice_status(provider_job_id)
            voice_model_id = provider_job_id
        else:
            raise ValueError(f"Unsupported voice provider: {provider}")

        if db_session and client_id:
            job = VoiceCloneJobModel(
                client_id=client_id,
                agent_profile_id=agent_profile_id,
                provider=provider.value,
                voice_name=voice_name,
                sample_file_path=file_path,
                status="ACTIVE",
                provider_job_id=provider_job_id,
                voice_model_id=voice_model_id,
            )
            db_session.add(job)
            await db_session.flush()
            logger.info("Voice clone job persisted — id=%s voice_model_id=%s", job.id, voice_model_id)

            if agent_profile_id:
                from sqlalchemy import update
                from database.models import AgentProfile
                stmt = (
                    update(AgentProfile)
                    .where(AgentProfile.id == agent_profile_id)
                    .values(voice_clone_id=voice_model_id)
                )
                await db_session.execute(stmt)
                logger.info("AgentProfile %s updated with voice_clone_id=%s", agent_profile_id, voice_model_id)

        return {
            "voice_model_id": voice_model_id,
            "provider": provider.value,
            "status": "ACTIVE",
            "voice_name": voice_name,
        }

    except Exception as exc:
        logger.error("Voice cloning failed: %s", exc, exc_info=True)
        if db_session and client_id:
            job = VoiceCloneJobModel(
                client_id=client_id,
                agent_profile_id=agent_profile_id,
                provider=provider.value,
                voice_name=voice_name,
                sample_file_path=file_path,
                status="FAILED",
                error_message=str(exc),
            )
            db_session.add(job)
            await db_session.flush()
        raise


async def list_elevenlabs_voices() -> list[dict]:
    """List all available ElevenLabs voices for the account."""
    api_key = _get_elevenlabs_key()
    url = f"{ELEVENLABS_BASE}/voices"
    headers = {"xi-api-key": api_key}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    return data.get("voices", [])


async def delete_elevenlabs_voice(voice_id: str) -> bool:
    """Delete a cloned voice from ElevenLabs."""
    api_key = _get_elevenlabs_key()
    url = f"{ELEVENLABS_BASE}/voices/{voice_id}"
    headers = {"xi-api-key": api_key}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(url, headers=headers)
        resp.raise_for_status()
    logger.info("ElevenLabs voice deleted: %s", voice_id)
    return True

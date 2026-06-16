"""LiveKit integration helpers (token generation, room management) - skeleton.

This module exposes small helpers to generate LiveKit join tokens and
manage simple room lifecycle tasks. Production requires `livekit` SDK.
"""
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def generate_join_token(identity: str, room: str) -> dict:
    # In production use livekit-server SDK to mint tokens with API key/secret
    # Here we return a placeholder token object for prototype use.
    token = f"mock-token-{identity}-{room}"
    url = settings.livekit_host
    return {"token": token, "url": url}

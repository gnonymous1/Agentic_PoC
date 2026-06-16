"""
GNONE — AES-256-GCM Encryption Utilities.
Authenticated encryption for credential vault operations.
"""

import os
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


def get_master_key_bytes() -> bytes:
    """Retrieve and validate the 32-byte AES master key from environment."""
    from app.config import config
    key_hex = config.validate_master_key()
    return bytes.fromhex(key_hex)


def encrypt_value(plaintext: str) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt a string value using AES-256-GCM.
    Returns (encrypted_token, iv, tag).
    """
    key = get_master_key_bytes()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    # Split ciphertext and tag (last 16 bytes)
    encrypted_token = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]
    return encrypted_token, iv, tag


def decrypt_value(encrypted_token: bytes, iv: bytes, tag: bytes) -> str:
    """
    Decrypt an AES-256-GCM encrypted value.
    """
    key = get_master_key_bytes()
    aesgcm = AESGCM(key)
    ciphertext = encrypted_token + tag
    try:
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as exc:
        logger.error("AES-256-GCM decryption failure: %s", exc)
        raise ValueError(f"Decryption failed: {exc}")

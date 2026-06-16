"""
AES-256-GCM application-level encryption/decryption for OAuth token vault with key version support.
See the architectural note in migrations/001_multi_tenant_schema.sql for key management strategy.
"""

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key(key_version: int = 1) -> bytes:
    env_var = f"ENCRYPTION_KEY_V{key_version}"
    key_hex = os.getenv(env_var)
    if not key_hex:
        raise RuntimeError(
            f"{env_var} environment variable not set. "
            f"Generate a 32-byte (64 hex char) key with: "
            f"openssl rand -hex 32"
        )
    return bytes.fromhex(key_hex)


def _get_latest_key_version() -> int:
    version = 1
    while os.getenv(f"ENCRYPTION_KEY_V{version + 1}"):
        version += 1
    return version


def encrypt_token(plaintext: str, key_version: int | None = None) -> tuple[bytes, bytes, bytes]:
    """
    Encrypt an OAuth token using AES-256-GCM.

    Args:
        plaintext: The OAuth token string to encrypt.
        key_version: The key version to use (defaults to latest).

    Returns:
        (ciphertext, iv, tag) — store all three in oauth_vault columns.
    """
    if key_version is None:
        key_version = _get_latest_key_version()
    key = _load_key(key_version)
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    ciphertext_with_tag = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    tag = ciphertext_with_tag[-16:]
    ct = ciphertext_with_tag[:-16]
    return ct, iv, tag


def decrypt_token(ct: bytes, iv: bytes, tag: bytes, key_version: int | None = None) -> str:
    """
    Decrypt an OAuth token that was encrypted with `encrypt_token`.

    Args:
        ct: stored ciphertext bytes
        iv: stored 12-byte nonce
        tag: stored 16-byte GCM authentication tag
        key_version: The key version used for encryption (defaults to latest).

    Returns:
        Decrypted plaintext string.
    """
    if key_version is None:
        key_version = _get_latest_key_version()
    key = _load_key(key_version)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(iv, ct + tag, None)
    return plaintext.decode("utf-8")


async def rotate_key(
    read_callback,
    write_callback,
    new_key_version: int | None = None,
) -> None:
    """
    Rotate encryption keys for all stored tokens.

    Args:
        read_callback: Async callable that returns a list of tuples
            (row_id, ct, iv, tag, key_version).
        write_callback: Async callable that accepts
            (row_id, new_ct, new_iv, new_tag, new_key_version).
        new_key_version: The target key version to rotate to (defaults to latest + 1).
    """
    if new_key_version is None:
        new_key_version = _get_latest_key_version() + 1

    rows = await read_callback()
    for row in rows:
        row_id, ct, iv, tag, old_key_version = row
        plaintext = decrypt_token(ct, iv, tag, key_version=old_key_version)
        new_ct, new_iv, new_tag = encrypt_token(plaintext, key_version=new_key_version)
        await write_callback(row_id, new_ct, new_iv, new_tag, new_key_version)


def generate_key() -> str:
    """Generate a new 32-byte hex-encoded AES-256 key."""
    return AESGCM.generate_key(bit_length=256).hex()

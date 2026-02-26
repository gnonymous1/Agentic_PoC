import os
from cryptography.fernet import Fernet
from pathlib import Path

# Path to the secret key file
KEY_FILE = Path(".secret.key")

def _get_key():
    """Get the encryption key, generating it if it doesn't exist."""
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
    else:
        with open(KEY_FILE, "rb") as f:
            key = f.read()
    return key

_cipher = None

def _get_cipher():
    """Get the Fernet cipher instance."""
    global _cipher
    if _cipher is None:
        key = _get_key()
        _cipher = Fernet(key)
    return _cipher

def encrypt_value(value: str) -> str:
    """Encrypt a string value."""
    if not value:
        return value
    cipher = _get_cipher()
    # Fernet.encrypt returns bytes, we decode to string for storage
    return cipher.encrypt(value.encode()).decode()

def decrypt_value(value: str) -> str:
    """Decrypt a string value. Returns original value if decryption fails."""
    if not value:
        return value
    try:
        cipher = _get_cipher()
        # Fernet.decrypt expects bytes
        return cipher.decrypt(value.encode()).decode()
    except Exception:
        # If decryption fails (e.g. invalid token, wrong key, or plaintext), return original
        return value

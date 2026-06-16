import os

from app.services.encryption import decrypt_token, encrypt_token, generate_key


def test_encrypt_decrypt_roundtrip():
    # Ensure keys available for test — generate a temporary key if not set
    key_env = os.getenv("ENCRYPTION_KEY_V1")
    if not key_env:
        os.environ["ENCRYPTION_KEY_V1"] = generate_key()

    plaintext = "test-token-12345"
    ct, iv, tag = encrypt_token(plaintext)
    decrypted = decrypt_token(ct, iv, tag)
    assert decrypted == plaintext

"""ExecMind - AES-256-GCM file encryption utilities."""

import os
from base64 import b64decode, b64encode

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings
from app.utils.logging import get_logger

logger = get_logger("encryption")

NONCE_SIZE = 12  # bytes for AES-GCM


def _get_master_key() -> bytes:
    """Get the master encryption key from settings.

    Returns:
        32-byte key derived from the hex-encoded master key.
    """
    key_hex = settings.MASTER_ENCRYPTION_KEY
    if not key_hex:
        raise ValueError("MASTER_ENCRYPTION_KEY is not configured.")
    return bytes.fromhex(key_hex)


def encrypt_file(source_path: str, dest_path: str) -> None:
    """Encrypt a file using AES-256-GCM with a per-file key.

    The per-file key is encrypted with the master key and stored alongside.

    Args:
        source_path: Path to the plaintext file.
        dest_path: Path for the encrypted output (.enc).
    """
    # Generate per-file key
    file_key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(file_key)

    with open(source_path, "rb") as f:
        plaintext = f.read()

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Write nonce + ciphertext
    with open(dest_path, "wb") as f:
        f.write(nonce + ciphertext)

    # Encrypt file key with master key and store
    master_aesgcm = AESGCM(_get_master_key())
    key_nonce = os.urandom(NONCE_SIZE)
    encrypted_key = master_aesgcm.encrypt(key_nonce, file_key, None)

    key_path = dest_path.replace(".enc", ".key")
    with open(key_path, "wb") as f:
        f.write(key_nonce + encrypted_key)

    logger.info("file_encrypted", dest=dest_path)


def decrypt_file(enc_path: str) -> bytes:
    """Decrypt a file encrypted with encrypt_file.

    Args:
        enc_path: Path to the encrypted file (.enc).

    Returns:
        Decrypted file contents as bytes.
    """
    # Load and decrypt the per-file key
    key_path = enc_path.replace(".enc", ".key")
    with open(key_path, "rb") as f:
        key_data = f.read()

    key_nonce = key_data[:NONCE_SIZE]
    encrypted_key = key_data[NONCE_SIZE:]

    master_aesgcm = AESGCM(_get_master_key())
    file_key = master_aesgcm.decrypt(key_nonce, encrypted_key, None)

    # Decrypt the file
    with open(enc_path, "rb") as f:
        enc_data = f.read()

    nonce = enc_data[:NONCE_SIZE]
    ciphertext = enc_data[NONCE_SIZE:]

    aesgcm = AESGCM(file_key)
    return aesgcm.decrypt(nonce, ciphertext, None)

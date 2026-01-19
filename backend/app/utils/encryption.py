"""
Encryption utilities for securely storing API keys at rest.
Uses Fernet symmetric encryption (AES-128-CBC).
"""

import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_fernet() -> Fernet:
    """
    Get a Fernet instance for encryption/decryption.
    The encryption key is derived from the ENCRYPTION_KEY setting.
    """
    settings = get_settings()

    # Derive a proper 32-byte key from the settings key
    # This allows using any string as the encryption key
    key_bytes = settings.encryption_key.encode()
    derived_key = hashlib.sha256(key_bytes).digest()
    fernet_key = base64.urlsafe_b64encode(derived_key)

    return Fernet(fernet_key)


def encrypt_api_key(api_key: str) -> bytes:
    """
    Encrypt an API key for secure storage.

    Args:
        api_key: The plaintext API key

    Returns:
        Encrypted bytes that can be stored in the database
    """
    fernet = get_fernet()
    return fernet.encrypt(api_key.encode())


def decrypt_api_key(encrypted_key: bytes) -> str:
    """
    Decrypt an API key from storage.

    Args:
        encrypted_key: The encrypted bytes from the database

    Returns:
        The plaintext API key

    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    fernet = get_fernet()
    try:
        return fernet.decrypt(encrypted_key).decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt API key - invalid token or wrong encryption key")
        raise ValueError("Failed to decrypt API key. The encryption key may have changed.") from e


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """
    Mask an API key for display, showing only the last few characters.

    Args:
        api_key: The plaintext API key
        visible_chars: Number of characters to show at the end

    Returns:
        Masked key like "sk-...abc123"
    """
    if len(api_key) <= visible_chars:
        return "*" * len(api_key)

    prefix = api_key[:3] if api_key.startswith(("sk-", "pk-")) else ""
    suffix = api_key[-visible_chars:]

    return f"{prefix}...{suffix}"

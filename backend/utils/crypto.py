"""Small at-rest encryption helpers for SMTP credentials."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret_key: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_secret(value: str, secret_key: str) -> str:
    if not value:
        return ""
    return _fernet(secret_key).encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str, secret_key: str) -> str:
    """Decrypt a stored secret; returns "" when empty or undecryptable.

    An undecryptable value means SECRET_KEY changed after the secret was
    stored — treat it as "no usable password" instead of crashing.
    """
    if not value:
        return ""
    try:
        return _fernet(secret_key).decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""

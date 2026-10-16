"""Password hashing helpers.

The browser-facing credential remains the lowercase SHA-256 digest used by the
legacy UI. The database stores a salted PBKDF2 hash of that digest.
"""

from __future__ import annotations

import hashlib

from werkzeug.security import check_password_hash, generate_password_hash


PBKDF2_METHOD = "pbkdf2:sha256:600000"


def client_password_digest(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password_digest(password_digest: str) -> str:
    return generate_password_hash(password_digest, method=PBKDF2_METHOD)


def verify_password_digest(password_hash: str, password_digest: str) -> bool:
    return check_password_hash(password_hash, password_digest)

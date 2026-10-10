"""Password and secret hashing.

Uses the standard library only (PBKDF2-HMAC-SHA256) to avoid heavy native
dependencies while remaining appropriate for a self-hosted home server.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$", 3)
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    expected = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), int(iterations)
    )
    return hmac.compare_digest(expected.hex(), digest)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
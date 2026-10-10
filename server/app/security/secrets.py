"""Device credentials and enrollment-code secrets.

Device credentials are high-entropy random tokens.  We store:
  * ``credential_id``: SHA-256 of the full token, indexed for O(1) lookup.
  * ``credential_hash``: PBKDF2 hash for verification (defence in depth).

The raw token is returned exactly once, to the enrolling agent.
"""

from __future__ import annotations

import secrets
import uuid

from .passwords import hash_password, sha256_hex, verify_password

_CRED_PREFIX = "nq"


def generate_device_credential(device_id: str | None = None) -> tuple[str, str, str]:
    """Return ``(raw_token, credential_id, credential_hash)``."""
    device_id = device_id or str(uuid.uuid4())
    secret = secrets.token_urlsafe(32)
    raw = f"{_CRED_PREFIX}_{device_id}_{secret}"
    return raw, sha256_hex(raw), hash_password(raw)


def credential_id_for(raw_token: str) -> str:
    return sha256_hex(raw_token)


def verify_device_credential(raw_token: str, credential_hash: str) -> bool:
    return verify_password(raw_token, credential_hash)


def generate_enrollment_code() -> tuple[str, str]:
    """Return ``(raw_code, code_hash)`` for a single-use enrollment code."""
    raw = secrets.token_urlsafe(18)
    return raw, hash_enrollment_code(raw)


def hash_enrollment_code(raw_code: str) -> str:
    return sha256_hex(raw_code)


def generate_opaque_token(nbytes: int = 16) -> str:
    return secrets.token_urlsafe(nbytes)
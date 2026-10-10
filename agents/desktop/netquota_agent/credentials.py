"""Secure local credential storage.

Preferred: the OS keyring (Windows Credential Manager / Secret Service on
Linux). Fallback: a file with 0600 permissions on POSIX and a restrictive ACL
on Windows. The raw device credential is never written to logs.
"""

from __future__ import annotations

import os
import platform
import stat

from .config import credential_path

_SERVICE = "netquota-agent"


def _keyring():
    try:
        import keyring  # type: ignore

        return keyring
    except Exception:  # pragma: no cover - optional dependency
        return None


def store_credential(device_id: str, credential: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(_SERVICE, device_id, credential)
            return
        except Exception:
            pass
    _store_file(device_id, credential)


def load_credential(device_id: str) -> str | None:
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(_SERVICE, device_id)
            if value:
                return value
        except Exception:
            pass
    return _load_file(device_id)


def delete_credential(device_id: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(_SERVICE, device_id)
        except Exception:
            pass
    path = credential_path()
    if path.exists():
        path.unlink()


def _store_file(device_id: str, credential: str) -> None:
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{device_id}\n{credential}\n", encoding="utf-8")
    _restrict(path)


def _load_file(device_id: str) -> str | None:
    path = credential_path()
    if not path.exists():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None
    stored_id, credential = lines[0], lines[1]
    if stored_id != device_id:
        return None
    return credential


def _restrict(path) -> None:
    try:
        if platform.system() == "Windows":
            # Best-effort: remove inherited access via icacls.
            os.system(f'icacls "{path}" /inheritance:r /grant:r "%USERNAME%":F >NUL 2>&1')
        else:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:  # pragma: no cover
        pass
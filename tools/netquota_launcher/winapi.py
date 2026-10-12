"""Windows-specific helpers used by the launcher.

Everything here is import-safe on non-Windows platforms; the Windows calls are
made lazily so the module can still be imported (and its pure helpers tested)
elsewhere.
"""

from __future__ import annotations

import ctypes
import platform
import socket
import sys
from pathlib import Path
from typing import Callable

IS_WINDOWS = platform.system() == "Windows"

CREATE_NO_WINDOW = 0x08000000
_ERROR_ALREADY_EXISTS = 183
_ATTACH_PARENT_PROCESS = ctypes.c_uint(-1) if IS_WINDOWS else None

_KEEPALIVE: list = []


def no_window_kwargs() -> dict:
    """Popen kwargs that prevent a console/child window from appearing."""
    if not IS_WINDOWS:
        return {}
    return {"creationflags": CREATE_NO_WINDOW}


# --------------------------------------------------------------------------- #
# Console handling


def attach_parent_console() -> bool:
    """Attach to the invoking console (if any) so CLI output is visible."""
    if not IS_WINDOWS:
        return False
    kernel32 = ctypes.windll.kernel32
    if not kernel32.AttachConsole(_ATTACH_PARENT_PROCESS):
        return False
    try:
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1, errors="replace")
        try:
            sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        except OSError:
            pass
    except OSError:
        return False
    return True


def ensure_streams(fallback_path: Path) -> None:
    """Make sure ``print`` works even in a windowed build with no console."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    redirect_std_to(fallback_path)


def redirect_std_to(path: Path) -> None:
    """Send stdout/stderr to *path* (used by the windowless background instance)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = open(path, "a", encoding="utf-8", buffering=1, errors="replace")
    sys.stdout = stream
    sys.stderr = stream


def hide_console() -> None:
    """Hide this process's console window (the login/background instance)."""
    if not IS_WINDOWS:
        return
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE


SW_HIDE = 0
SW_SHOWNORMAL = 1


# --------------------------------------------------------------------------- #
# Single instance


def single_instance(name: str) -> bool:
    """Return True if this process acquired the named mutex (is the only one)."""
    if not IS_WINDOWS:
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, True, name)
    if not handle:
        return True
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return False
    _KEEPALIVE.append(handle)
    return True


# --------------------------------------------------------------------------- #
# Ports & processes


def port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def iter_processes():
    """Yield ``{pid, name, exe, cmdline}`` for every readable process."""
    import psutil

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            info = proc.info
        except Exception:  # pragma: no cover - process vanished mid-iteration
            continue
        yield {
            "pid": info.get("pid"),
            "name": info.get("name") or "",
            "exe": info.get("exe") or "",
            "cmdline": info.get("cmdline") or [],
        }


def kill_pids(pids) -> None:
    import psutil

    for pid in pids:
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass


def kill_matching(predicate: Callable[[dict], bool]) -> int:
    pids = [info["pid"] for info in iter_processes() if predicate(info)]
    kill_pids(pids)
    return len(pids)


def pids_on_port(port: int) -> list[int]:
    import psutil

    pids: list[int] = []
    try:
        connections = psutil.net_connections(kind="tcp")
    except Exception:  # pragma: no cover - needs privileges on some systems
        return pids
    for conn in connections:
        if (
            conn.status == psutil.CONN_LISTEN
            and conn.laddr
            and getattr(conn.laddr, "port", None) == port
            and conn.pid
        ):
            pids.append(conn.pid)
    return pids


# --------------------------------------------------------------------------- #
# Shortcut creation (IShellLinkW via COM, no WScript dependency)


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_string(cls, value: str) -> "_GUID":
        guid = cls()
        result = ctypes.windll.ole32.CLSIDFromString(
            ctypes.c_wchar_p(value), ctypes.byref(guid)
        )
        if result != 0:
            raise OSError(f"CLSIDFromString({value!r}) failed: 0x{result & 0xFFFFFFFF:08x}")
        return guid


_CLSID_SHELLLINK = "{00021401-0000-0000-C000-000000000046}"
_IID_ISHELLLINKW = "{000214F9-0000-0000-C000-000000000046}"
_IID_IPERSISTFILE = "{0000010b-0000-0000-C000-000000000046}"


def create_shortcut(
    lnk_path: Path,
    target: Path,
    arguments: str = "",
    working_dir: Path | None = None,
    description: str = "",
    show_cmd: int | None = None,
) -> None:
    """Create a .lnk without depending on WScript.Shell / wscript.exe."""
    if not IS_WINDOWS:
        raise RuntimeError("shortcuts are only supported on Windows")

    ole32 = ctypes.windll.ole32
    ole32.CoInitialize(None)

    shell_link = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(
        ctypes.byref(_GUID.from_string(_CLSID_SHELLLINK)),
        None,
        1,  # CLSCTX_INPROC_SERVER
        ctypes.byref(_GUID.from_string(_IID_ISHELLLINKW)),
        ctypes.byref(shell_link),
    )
    if hr != 0:
        raise OSError(f"CoCreateInstance(ShellLink) failed: 0x{hr & 0xFFFFFFFF:08x}")

    vtable = ctypes.cast(shell_link, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]

    def method(index: int, *argtypes):
        proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
        return proto(vtable[index])

    set_path = method(20, ctypes.c_wchar_p)
    set_workdir = method(9, ctypes.c_wchar_p)
    set_args = method(11, ctypes.c_wchar_p)
    set_desc = method(7, ctypes.c_wchar_p)
    set_show_cmd = method(15, ctypes.c_int)
    query_interface = method(
        0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)
    )
    release = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)

    try:
        set_path(shell_link, str(target))
        if working_dir is not None:
            set_workdir(shell_link, str(working_dir))
        if arguments:
            set_args(shell_link, arguments)
        if description:
            set_desc(shell_link, description)
        if show_cmd is not None:
            set_show_cmd(shell_link, show_cmd)

        persist = ctypes.c_void_p()
        hr = query_interface(
            shell_link,
            ctypes.byref(_GUID.from_string(_IID_IPERSISTFILE)),
            ctypes.byref(persist),
        )
        if hr != 0:
            raise OSError(f"QueryInterface(IPersistFile) failed: 0x{hr & 0xFFFFFFFF:08x}")

        persist_vtable = ctypes.cast(
            persist, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))
        )[0]
        save = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_long)(
            persist_vtable[6]
        )
        Path(lnk_path).parent.mkdir(parents=True, exist_ok=True)
        hr = save(persist, str(lnk_path), 1)
        if hr != 0:
            raise OSError(f"IPersistFile.Save failed: 0x{hr & 0xFFFFFFFF:08x}")
        release(persist_vtable[2])(persist)
    finally:
        release(vtable[2])(shell_link)

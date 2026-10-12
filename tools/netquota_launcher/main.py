"""net-quota launcher / supervisor.

Commands::

    net-quota run               Start the role's components and keep them alive (default)
    net-quota stop              Stop every NetQuota component
    net-quota status            Show what is running
    net-quota install           Record role/repo, install to %ProgramData%, add to PATH
    net-quota install -Startup  Also auto-start at login (Startup shortcut)
    net-quota help              Show help

Internal entry point used by the supervisor to run the agent:

    net-quota _agent
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import __version__, paths, winapi
from .plan import plan_components
from .supervisor import Supervisor

POLL_SECONDS = 3.0
COOLDOWN_SECONDS = 15.0
SUPERVISOR_MUTEX = r"Local\NetQuotaSupervisor"
INSTALLED_EXE_NAME = "net-quota.exe"
LEGACY_STARTUP_LINKS = ("NetQuota Auto-Start.lnk", "NetQuota Agent.lnk")


# --------------------------------------------------------------------------- #
# Small helpers


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _launcher_agent_argv() -> list[str]:
    if _is_frozen():
        return [str(Path(sys.executable)), "_agent"]
    return [str(Path(sys.executable)), "-m", "netquota_launcher", "_agent"]


def _python_exe(repo: Path | None) -> Path:
    if repo:
        for rel in ("server/.venv/Scripts/python.exe", "server/.venv/bin/python"):
            candidate = Path(repo) / rel
            if candidate.exists():
                return candidate
    return Path(sys.executable)


def _resolve_repo(data: Path, args) -> Path | None:
    override = getattr(args, "repo", "")
    if override:
        return Path(override)
    cfg = paths.read_launcher_config(data)
    if cfg.repo_root and cfg.repo_root.is_dir():
        return cfg.repo_root
    starts: list[Path] = []
    if _is_frozen():
        starts.append(Path(sys.executable).parent)
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve().parent)
    for start in starts:
        found = paths.find_repo(start)
        if found:
            return found
    return None


def _startup_dir() -> Path:
    return (
        Path(os.environ["APPDATA"])
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


# --------------------------------------------------------------------------- #
# Process selectors used by stop()


def _is_agent_child(info: dict) -> bool:
    return "_agent" in info["cmdline"]


def _is_legacy_agent(info: dict) -> bool:
    joined = " ".join(info["cmdline"]).lower()
    return "netquota-agent" in joined or "netquota_agent" in joined


def _is_supervisor(info: dict) -> bool:
    if info["name"].lower() != INSTALLED_EXE_NAME:
        return False
    cmd = [c.lower() for c in info["cmdline"]]
    return "_agent" not in cmd and "run" in cmd


def _is_legacy_supervisor(info: dict) -> bool:
    joined = " ".join(info["cmdline"]).lower()
    return "net-quota.ps1" in joined and " run" in joined


def _is_uvicorn(info: dict) -> bool:
    joined = " ".join(info["cmdline"])
    return "uvicorn" in joined and "app.main:app" in joined


def _is_npm_dev(info: dict) -> bool:
    joined = " ".join(info["cmdline"])
    return "run dev" in joined and ("npm" in joined or "node" in info["name"].lower())


# --------------------------------------------------------------------------- #
# run


def _spawn(component, children: dict, log_dir: Path) -> None:
    env = os.environ.copy()
    if component.kind == "backend":
        env.setdefault("NETQUOTA_DATABASE_URL", "sqlite+aiosqlite:///./netquota.db")
        env.setdefault("NETQUOTA_ADMIN_BOOTSTRAP_PASSWORD", "changeme")
    out = open(log_dir / f"{component.name}.log", "ab")
    err = open(log_dir / f"{component.name}.err.log", "ab")
    try:
        proc = subprocess.Popen(
            [str(a) for a in component.argv],
            cwd=str(component.cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            **winapi.no_window_kwargs(),
        )
    finally:
        out.close()
        err.close()
    children[component.name] = proc
    print(f"  [start] {component.name}")


def _stop_children(children: dict) -> None:
    for proc in list(children.values()):
        try:
            proc.terminate()
        except Exception:
            pass
    deadline = time.time() + 5
    for proc in list(children.values()):
        try:
            proc.wait(timeout=max(0.1, deadline - time.time()))
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def cmd_run(_args) -> int:
    data = paths.data_dir()
    log_dir = paths.log_dir(data)
    log_dir.mkdir(parents=True, exist_ok=True)

    repo = _resolve_repo(data, _args)
    role = paths.resolve_role(data, repo)
    base = repo or Path.cwd()
    components = plan_components(
        role,
        base,
        python_exe=_python_exe(repo),
        launcher_exe=Path(sys.executable),
        npm_cmd="npm",
    )
    if not _is_frozen():
        for component in components:
            if component.kind == "agent":
                component.argv = _launcher_agent_argv()

    if not winapi.single_instance(SUPERVISOR_MUTEX):
        print("A net-quota supervisor is already running (see: net-quota status).")
        return 0

    stop = paths.stop_flag(data)
    try:
        stop.unlink()
    except FileNotFoundError:
        pass

    children: dict[str, subprocess.Popen] = {}

    def is_up(component) -> bool:
        if component.kind == "agent":
            proc = children.get("agent")
            return proc is not None and proc.poll() is None
        if component.port:
            return winapi.port_listening(component.port)
        return False

    def start(component) -> None:
        _spawn(component, children, log_dir)

    supervisor = Supervisor(
        components, is_up=is_up, start=start, cooldown=COOLDOWN_SECONDS
    )
    print(f"net-quota supervisor (role={role}). Logs: {log_dir}")
    try:
        supervisor.run(stop_requested=lambda: stop.exists(), poll_seconds=POLL_SECONDS)
    finally:
        _stop_children(children)
    return 0


# --------------------------------------------------------------------------- #
# stop / status


def cmd_stop(_args) -> int:
    data = paths.data_dir()
    paths.log_dir(data).mkdir(parents=True, exist_ok=True)
    stop = paths.stop_flag(data)
    stop.write_text("stop", encoding="utf-8")

    deadline = time.time() + 8
    while time.time() < deadline and any(
        _is_supervisor(info) or _is_legacy_supervisor(info)
        for info in winapi.iter_processes()
    ):
        time.sleep(0.5)

    for _ in range(6):
        pids: set[int] = set()
        for info in winapi.iter_processes():
            if (
                _is_agent_child(info)
                or _is_legacy_agent(info)
                or _is_uvicorn(info)
                or _is_supervisor(info)
                or _is_legacy_supervisor(info)
                or _is_npm_dev(info)
            ):
                pids.add(info["pid"])
        pids.update(winapi.pids_on_port(8000))
        pids.update(winapi.pids_on_port(5173))
        if not pids:
            break
        winapi.kill_pids(pids)
        time.sleep(0.4)

    try:
        stop.unlink()
    except FileNotFoundError:
        pass
    print("Stopped.")
    return 0


def cmd_status(_args) -> int:
    data = paths.data_dir()
    repo = _resolve_repo(data, _args)
    role = paths.resolve_role(data, repo)

    rows = [
        ("backend", winapi.port_listening(8000), ":8000"),
        ("dashboard", winapi.port_listening(5173), ":5173"),
        ("agent", any(_is_agent_child(i) for i in winapi.iter_processes()), ""),
    ]
    if role == "agent":
        rows = [row for row in rows if row[0] == "agent"]

    print(f"NetQuota status  (role={role})")
    for name, up, detail in rows:
        print(f"  {name:<10} {'UP' if up else 'down':<5} {detail}")
    return 0


# --------------------------------------------------------------------------- #
# install


def _add_to_user_path(directory: str) -> None:
    if not winapi.IS_WINDOWS:
        return
    import winreg

    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE
    )
    try:
        raw, kind = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        raw, kind = "", winreg.REG_EXPAND_SZ
    parts = [p for p in str(raw).split(";") if p and p != directory]
    winreg.SetValueEx(key, "Path", 0, kind, ";".join([directory, *parts]))
    winreg.CloseKey(key)
    print(f"On user PATH: {directory}")
    _broadcast_environment()


def _broadcast_environment() -> None:
    if not winapi.IS_WINDOWS:
        return
    import ctypes

    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(
        0xFFFF,  # HWND_BROADCAST
        0x1A,  # WM_SETTINGCHANGE
        0,
        ctypes.c_wchar_p("Environment"),
        0x2,  # SMTO_ABORTIFHUNG
        5000,
        ctypes.byref(result),
    )


def _install_startup(target: Path, workdir: Path) -> None:
    lnk = _startup_dir() / "NetQuota.lnk"
    winapi.create_shortcut(
        lnk,
        target,
        arguments="run -Background",
        working_dir=workdir,
        description="NetQuota",
        show_cmd=winapi.SW_HIDE,
    )
    print(f"Installed login auto-start: {lnk}")


def _remove_legacy_startup() -> None:
    startup = _startup_dir()
    for name in LEGACY_STARTUP_LINKS:
        legacy = startup / name
        if legacy.exists():
            legacy.unlink()
            print(f"Removed old auto-start: {legacy}")


def cmd_install(args) -> int:
    data = paths.data_dir()
    paths.log_dir(data).mkdir(parents=True, exist_ok=True)

    repo = _resolve_repo(data, args)
    role = getattr(args, "role", "") or paths.resolve_role(data, repo)

    # Stop anything running so the installed exe can be replaced safely.
    cmd_stop(args)

    installed = data / INSTALLED_EXE_NAME
    if _is_frozen():
        src = Path(sys.executable).resolve()
        if src != installed.resolve():
            shutil.copy2(src, installed)
            print(f"Installed launcher: {installed}")
        start_argv = [str(installed), "run", "-Background"]
    else:
        print("Dev mode: not copying the exe or writing a login shortcut.")
        start_argv = [str(Path(sys.executable)), "-m", "netquota_launcher", "run", "-Background"]

    paths.role_file(data).write_text(role, encoding="utf-8")
    paths.write_launcher_config(data, paths.LauncherConfig(repo_root=repo))
    print(f"Role set to '{role}'.")
    if repo:
        print(f"Repo root: {repo}")

    _add_to_user_path(str(data))

    if getattr(args, "startup", False) and _is_frozen():
        _install_startup(installed, repo or data)
    _remove_legacy_startup()

    try:
        subprocess.Popen(
            start_argv,
            cwd=str(repo or data),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **winapi.no_window_kwargs(),
        )
        print("Started net-quota.")
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Could not start supervisor: {exc}")
    return 0


# --------------------------------------------------------------------------- #
# entry points


def _run_agent() -> int:
    data = paths.data_dir()
    winapi.ensure_streams(paths.log_dir(data) / "agent.log")
    from netquota_agent.main import main as agent_main

    return agent_main(["run"]) or 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="net-quota", description="NetQuota launcher")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "stop", "status", "install", "help"],
    )
    parser.add_argument("-Role", "--role", dest="role", choices=["host", "agent"], default="")
    parser.add_argument("-Startup", "--startup", dest="startup", action="store_true")
    parser.add_argument("-Repo", "--repo", dest="repo", default="")
    parser.add_argument(
        "-Background",
        "--background",
        dest="background",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "_agent":
        return _run_agent()

    data = paths.data_dir()
    args = _build_parser().parse_args(argv)
    if args.command == "help":
        _build_parser().print_help()
        return 0

    if args.background:
        # Started by the login shortcut: no visible window, output to logs.
        winapi.hide_console()
        winapi.redirect_std_to(paths.log_dir(data) / "net-quota.log")
    elif not winapi.attach_parent_console():
        winapi.ensure_streams(paths.log_dir(data) / "net-quota.log")

    return {
        "run": cmd_run,
        "stop": cmd_stop,
        "status": cmd_status,
        "install": cmd_install,
    }[args.command](args)

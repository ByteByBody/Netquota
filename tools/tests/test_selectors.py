"""Tests for the process selectors used by ``net-quota stop``.

These decide which processes are NetQuota's own, so a regression here could
either leave components running or kill an unrelated process.
"""

from netquota_launcher import main

EXE = r"C:\ProgramData\NetQuota\net-quota.exe"


def _proc(name, cmdline):
    return {"pid": 1, "name": name, "exe": "", "cmdline": cmdline}


def test_is_supervisor_matches_the_run_instance():
    assert main._is_supervisor(_proc("net-quota.exe", [EXE, "run", "-Background"]))


def test_is_supervisor_ignores_status_and_agent_modes():
    assert not main._is_supervisor(_proc("net-quota.exe", [EXE, "status"]))
    assert not main._is_supervisor(_proc("net-quota.exe", [EXE, "_agent"]))


def test_is_supervisor_ignores_other_programs():
    assert not main._is_supervisor(_proc("python.exe", ["python", "-m", "uvicorn", "run"]))


def test_is_agent_child_matches_agent_mode_only():
    assert main._is_agent_child(_proc("net-quota.exe", [EXE, "_agent"]))
    assert not main._is_agent_child(_proc("net-quota.exe", [EXE, "run"]))


def test_is_legacy_agent_matches_the_old_console_script():
    assert main._is_legacy_agent(_proc("netquota-agent.exe", [r"C:\x\Scripts\netquota-agent.exe", "run"]))
    assert main._is_legacy_agent(_proc("python.exe", ["python", "-c", "from netquota_agent.main import main"]))


def test_is_legacy_agent_does_not_match_the_bundled_agent():
    assert not main._is_legacy_agent(_proc("net-quota.exe", [EXE, "_agent"]))


def test_is_legacy_supervisor_matches_the_powershell_script_only_when_running():
    assert main._is_legacy_supervisor(
        _proc("powershell.exe", ["powershell", "-File", r"C:\x\bin\net-quota.ps1", "run"])
    )
    assert not main._is_legacy_supervisor(
        _proc("powershell.exe", ["powershell", "-File", r"C:\x\bin\net-quota.ps1", "status"])
    )

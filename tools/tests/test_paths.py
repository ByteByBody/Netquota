"""Tests for launcher path/role resolution."""

import os
import stat
from pathlib import Path

from netquota_launcher import paths


def test_data_dir_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("NETQUOTA_DATA_DIR", str(tmp_path))
    assert paths.data_dir() == tmp_path


def test_find_repo_walks_up_to_a_checkout(tmp_path):
    (tmp_path / "server").mkdir()
    (tmp_path / "agents").mkdir()
    deep = tmp_path / "tools" / "netquota_launcher"
    deep.mkdir(parents=True)
    assert paths.find_repo(deep) == tmp_path


def test_find_repo_returns_none_without_a_checkout(tmp_path):
    assert paths.find_repo(tmp_path) is None


def _make_host_venv(repo: Path) -> None:
    scripts = repo / "server" / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    (scripts / "python.exe").write_text("", encoding="utf-8")


def test_resolve_role_prefers_role_file_over_inference(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "role.txt").write_text("agent", encoding="utf-8")
    repo = tmp_path / "repo"
    _make_host_venv(repo)
    assert paths.resolve_role(data, repo) == "agent"


def test_resolve_role_infers_host_from_server_venv(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    repo = tmp_path / "repo"
    _make_host_venv(repo)
    assert paths.resolve_role(data, repo) == "host"


def test_resolve_role_defaults_to_agent(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    assert paths.resolve_role(data, repo) == "agent"


def test_resolve_role_ignores_unknown_role_value(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "role.txt").write_text("banana", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    assert paths.resolve_role(data, repo) == "agent"


def test_launcher_config_round_trips_repo_root(tmp_path):
    cfg = paths.LauncherConfig(repo_root=tmp_path / "repo")
    paths.write_launcher_config(tmp_path, cfg)
    loaded = paths.read_launcher_config(tmp_path)
    assert loaded.repo_root == tmp_path / "repo"


def test_resilient_write_creates_and_overwrites(tmp_path):
    target = tmp_path / "role.txt"
    assert paths.write_text_resilient(target, "agent") is True
    assert target.read_text(encoding="utf-8") == "agent"
    assert paths.write_text_resilient(target, "host") is True
    assert target.read_text(encoding="utf-8") == "host"


def test_resilient_write_leaves_an_already_correct_file_untouched(tmp_path):
    target = tmp_path / "role.txt"
    # A previous PowerShell install wrote the value with a trailing newline.
    target.write_bytes(b"agent\r\n")
    assert paths.write_text_resilient(target, "agent") is True
    assert target.read_bytes() == b"agent\r\n"


def test_resilient_write_recovers_from_a_read_only_file(tmp_path):
    target = tmp_path / "role.txt"
    target.write_text("agent", encoding="utf-8")
    os.chmod(target, stat.S_IREAD)
    try:
        assert paths.write_text_resilient(target, "host") is True
        assert target.read_text(encoding="utf-8") == "host"
    finally:
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)

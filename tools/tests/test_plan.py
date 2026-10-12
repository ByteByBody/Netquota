"""Tests for role -> component planning."""

from netquota_launcher import plan


def _plan(role, repo):
    return plan.plan_components(
        role,
        repo,
        python_exe=repo / "py.exe",
        launcher_exe=repo / "net-quota.exe",
        npm_cmd="npm",
    )


def test_agent_role_plans_only_the_agent(tmp_path):
    comps = _plan("agent", tmp_path)
    assert [c.kind for c in comps] == ["agent"]


def test_host_role_plans_backend_dashboard_and_agent(tmp_path):
    comps = _plan("host", tmp_path)
    assert [c.kind for c in comps] == ["backend", "dashboard", "agent"]


def test_backend_targets_uvicorn_on_8000_from_server_dir(tmp_path):
    backend = next(c for c in _plan("host", tmp_path) if c.kind == "backend")
    assert backend.cwd == tmp_path / "server"
    assert backend.port == 8000
    assert backend.argv[1:4] == ["-m", "uvicorn", "app.main:app"]


def test_dashboard_runs_npm_in_apps_dashboard_on_5173(tmp_path):
    dash = next(c for c in _plan("host", tmp_path) if c.kind == "dashboard")
    assert dash.cwd == tmp_path / "apps" / "dashboard"
    assert dash.port == 5173
    assert "npm run dev" in " ".join(dash.argv)


def test_agent_reexecs_the_launcher_in_agent_mode(tmp_path):
    agent = _plan("agent", tmp_path)[0]
    assert agent.argv[0] == str(tmp_path / "net-quota.exe")
    assert agent.argv[-1] == "_agent"

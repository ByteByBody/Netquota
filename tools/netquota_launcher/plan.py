"""Turn a machine role into the set of components the supervisor manages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Component:
    name: str
    kind: str  # "backend" | "dashboard" | "agent"
    cwd: Path
    argv: list[str]
    port: int | None = None


def plan_components(
    role: str,
    repo: Path,
    *,
    python_exe: Path,
    launcher_exe: Path,
    npm_cmd: str = "npm",
) -> list[Component]:
    repo = Path(repo)
    components: list[Component] = []

    if role == "host":
        components.append(
            Component(
                name="backend",
                kind="backend",
                cwd=repo / "server",
                port=8000,
                argv=[
                    str(python_exe),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ],
            )
        )
        components.append(
            Component(
                name="dashboard",
                kind="dashboard",
                cwd=repo / "apps" / "dashboard",
                port=5173,
                argv=["cmd.exe", "/c", f"{npm_cmd} run dev"],
            )
        )

    components.append(
        Component(
            name="agent",
            kind="agent",
            cwd=repo,
            argv=[str(launcher_exe), "_agent"],
        )
    )
    return components

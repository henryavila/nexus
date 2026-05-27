from __future__ import annotations

import typer

from nexus.config import NexusConfig
from nexus.services import ServiceContainer

app = typer.Typer(
    name="nexus",
    help="CLI para catalogar, escanear e lançar projetos de agentes IA",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        from nexus.tui import run_tui
        raise typer.Exit(run_tui())


def get_container() -> ServiceContainer:
    config = NexusConfig.load()
    data_repo = _detect_data_repo(config.data_dir)
    return ServiceContainer(config, data_repo_path=data_repo)


def _detect_data_repo(data_dir) -> str | None:
    import subprocess
    from pathlib import Path
    if not Path(data_dir).is_dir():
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(data_dir), capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


from nexus.cli import project_cmds  # noqa: E402, F401
from nexus.cli import idea_cmds  # noqa: E402, F401
from nexus.cli import app_cmds  # noqa: E402, F401
from nexus.cli import codex_cmds  # noqa: E402, F401
from nexus.cli import skill_cmds  # noqa: E402, F401
from nexus.cli import env_cmds  # noqa: E402, F401
from nexus.cli import scan_cmds  # noqa: E402, F401
from nexus.cli import sync_cmds  # noqa: E402, F401
from nexus.cli import init_cmd  # noqa: E402, F401
from nexus.cli import migrate_cmd  # noqa: E402, F401


@app.command("tui")
def tui_command(tab: str = typer.Option("ideas", "--tab", "-t", help="Tab inicial")):
    """Abrir interface TUI."""
    from nexus.tui import run_tui
    raise typer.Exit(run_tui(initial_tab=tab))


def main():
    app()

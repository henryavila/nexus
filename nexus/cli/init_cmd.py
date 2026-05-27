from __future__ import annotations
from pathlib import Path
import json

import typer
import yaml

from nexus.cli import app
from nexus.config import NexusConfig


@app.command("init")
def init(
    data_dir: str = typer.Option(None, "--data-dir", help="Caminho para o diretório de dados"),
):
    """Inicializar diretório de dados do Nexus."""
    if data_dir:
        config = NexusConfig(data_dir=Path(data_dir))
        config.save()
    else:
        config = NexusConfig.load()

    config.ensure_dirs()

    if not config.projects_yml.exists():
        config.projects_yml.write_text("projects: []\n", encoding="utf-8")
    if not config.apps_yml.exists():
        config.apps_yml.write_text("apps: []\n", encoding="utf-8")
    if not config.ideas_yml.exists():
        config.ideas_yml.write_text("ideas: []\n", encoding="utf-8")
    if not config.environments_yml.exists():
        config.environments_yml.write_text("environments: []\n", encoding="utf-8")
    if not config.data_json.exists():
        config.data_json.write_text(json.dumps({
            "version": "3.0", "last_full_scan": None, "current_environment": None,
            "projects": [], "apps": [], "environments": [], "ideas": [], "codex": [],
        }, indent=2), encoding="utf-8")

    typer.echo(f"✓ Diretório de dados inicializado em: {config.data_dir}")
